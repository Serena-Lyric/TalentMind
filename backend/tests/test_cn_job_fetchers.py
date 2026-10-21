import json
import shutil
import subprocess

from app.collect.fetchers.job_sites import (
    SITES,
    build_detail_extract_js,
    build_panel_probe_js,
    build_search_extract_js,
    deduplicate_jobs,
    normalize_job,
    normalize_url,
)
from app.collect.cn_collect_loop import QueryTarget, build_targets


def test_normalize_url_strips_tracking_query():
    spec = SITES["zhaopin"]
    assert normalize_url(spec, "/job/abc.html?sid=1") == "https://www.zhaopin.com/job/abc.html"
    assert normalize_url(spec, "/sou/?kw=Python") == ""


def test_liepin_normalizes_detail_url():
    spec = SITES["liepin"]
    assert normalize_url(spec, "https://www.liepin.com/job/123456/") == "https://www.liepin.com/job/123456"


def test_dedup_keeps_tags_from_richer_record():
    spec = SITES["zhaopin"]
    jobs = deduplicate_jobs(spec, [
        {"url": "/job/abc", "title": "Python 工程师"},
        {"url": "/job/abc?x=1", "title": "Python 工程师", "tags": ["本科"]},
    ])
    assert len(jobs) == 1
    assert jobs[0]["tags"] == ["本科"]


def test_normalize_job_returns_platform_source_and_raw_text():
    spec = SITES["liepin"]
    raw = normalize_job(spec, {
        "url": "/job/abc",
        "title": "数据工程师",
        "company": "示例公司",
        "tags": ["3-5年", "本科", "Python"],
    }, {"description": "负责数据平台建设", "company_info": "软件服务公司"})
    assert raw is not None
    assert raw.source == "liepin"
    assert raw.experience == ""
    assert "负责数据平台建设" in raw.raw_html
    assert raw.source_detail.endswith("/job/abc")


def test_build_targets_stable_order():
    assert build_targets(["Python", "Java"], [("北京", "530"), ("上海", "538")]) == [
        QueryTarget("Python", "北京", "530"),
        QueryTarget("Python", "上海", "538"),
        QueryTarget("Java", "北京", "530"),
        QueryTarget("Java", "上海", "538"),
    ]


def test_zhaopin_dom_identity_is_stable_and_kept_over_detail_url():
    spec = SITES["zhaopin"]
    assert normalize_url(spec, "dom://zhaopin/cfca7fe7") == "dom://zhaopin/cfca7fe7"
    raw = normalize_job(
        spec,
        {"url": "dom://zhaopin/cfca7fe7", "title": "Python 工程师"},
        {"url": "https://www.zhaopin.com/job/real-detail", "description": "负责平台开发"},
    )
    assert raw is not None
    assert raw.source_detail == "dom://zhaopin/cfca7fe7"


def test_dom_extract_scripts_include_current_site_selectors_without_extra_quotes():
    zhaopin_js = build_search_extract_js(SITES["zhaopin"])
    liepin_js = build_search_extract_js(SITES["liepin"])
    assert 'const cards = ".job-card' in zhaopin_js
    assert "dom://zhaopin/" in zhaopin_js
    assert "const titleRequired = false" in zhaopin_js
    assert "const titleRequired = true" in liepin_js
    assert 'const cards = ".job-list-item' in liepin_js
    assert "[class*='job-card']" in liepin_js
    for script in (zhaopin_js, liepin_js, build_detail_extract_js(SITES["zhaopin"]), build_detail_extract_js(SITES["liepin"])):
        assert "querySelectorAll(''" not in script
        assert "const cards = '" not in script


def test_zhaopin_search_script_emits_observation_key_and_list_url():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for actual extraction JavaScript")
    runner = r'''
const vm=require('node:vm'); let input='';
process.stdin.on('data',d=>input+=d);
process.stdin.on('end',()=>{
  const text=n=>({innerText:n.text,textContent:n.text,querySelectorAll:()=>[],getBoundingClientRect:()=>({width:100,height:100})});
  const title=text('Python 工程师'), company=text('甲公司'), salary=text('20-30K'), location=text('上海');
  const card={
    innerText:'Python 工程师 甲公司 20-30K 上海',
    querySelector:s=>s.includes('title')?title:s.includes('company')?company:s.includes('salary')?salary:s.includes('location')?location:null,
    querySelectorAll:s=>s.includes('[class*="tag"]')||s.startsWith('a')?[]:[],
    getBoundingClientRect:()=>({width:300,height:100})
  };
  const document={querySelectorAll:s=>s.includes('.job-card')?[card]:[]};
  const pageLocation={href:'https://www.zhaopin.com/jobs/?jl=538&kw=Java&page=1'};
  const value=vm.runInNewContext(input,{document,location:pageLocation,getComputedStyle:()=>({display:'block',visibility:'visible'})});
  process.stdout.write(JSON.stringify(value));
});'''
    done = subprocess.run(
        [node, '-e', runner],
        input=build_search_extract_js(SITES['zhaopin']),
        text=True,
        capture_output=True,
        encoding='utf-8',
        check=True,
    )
    result = json.loads(done.stdout)[0]
    assert result['_dom'] is True
    assert result['_list_url'].startswith('https://www.zhaopin.com/jobs/')
    assert result['_observation_key'].startswith('zhaopin:')


def test_identical_zhaopin_dom_cards_survive_before_detail_sampling():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for actual extraction JavaScript")
    runner = r'''
const vm=require('node:vm'); let input='';
process.stdin.on('data',d=>input+=d);
process.stdin.on('end',()=>{
  const text=value=>({innerText:value,textContent:value,querySelectorAll:()=>[],getBoundingClientRect:()=>({width:100,height:100})});
  const card=()=>({
    innerText:'后端工程师 甲公司 20-30K 上海',
    querySelector:s=>s.includes('title')?text('后端工程师'):
      s.includes('company')?text('甲公司'):
      s.includes('salary')?text('20-30K'):
      s.includes('location')?text('上海'):null,
    querySelectorAll:()=>[],
    getBoundingClientRect:()=>({width:300,height:100})
  });
  const document={querySelectorAll:s=>s.includes('.job-card')?[card(),card()]:[]};
  const pageLocation={href:'https://www.zhaopin.com/jobs/?jl=538&kw=Java&page=1'};
  const value=vm.runInNewContext(input,{document,location:pageLocation,getComputedStyle:()=>({display:'block',visibility:'visible'})});
  process.stdout.write(JSON.stringify(value));
});'''
    done = subprocess.run(
        [node, '-e', runner],
        input=build_search_extract_js(SITES['zhaopin']),
        text=True,
        capture_output=True,
        encoding='utf-8',
        check=True,
    )
    extracted = json.loads(done.stdout)
    jobs = deduplicate_jobs(SITES['zhaopin'], extracted)

    assert len(jobs) == 2
    assert jobs[0]['url'] != jobs[1]['url']
    assert jobs[0]['_observation_key'] != jobs[1]['_observation_key']


def test_zhaopin_panel_probe_reports_active_card_and_panel():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for actual extraction JavaScript")
    runner = r'''
const vm=require('node:vm'); let input='';
process.stdin.on('data',d=>input+=d);
process.stdin.on('end',()=>{
  const node=text=>({innerText:text,textContent:text,querySelectorAll:()=>[],getBoundingClientRect:()=>({width:100,height:100})});
  const cards=[{},{}];
  cards[1].classList={contains:value=>value==='job-card--active'};
  const panel={
    querySelectorAll:s=>s.includes('title')?[node('后端工程师')]:
      s.includes('company')?[node('乙公司')]:
      s.includes('salary')?[node('25-35K')]:
      s.includes('location')?[node('北京')]:
      s.includes('description__content')?[node('负责服务开发')]:[],
    getBoundingClientRect:()=>({width:600,height:800})
  };
  const document={
    querySelectorAll:s=>s.includes('.job-card')?cards:[],
    querySelector:s=>s==='.job-detail-panel'?panel:null
  };
  const pageLocation={href:'https://www.zhaopin.com/jobs/?jl=538&kw=Java&page=1'};
  const value=vm.runInNewContext(input,{document,location:pageLocation,getComputedStyle:()=>({display:'block',visibility:'visible'})});
  process.stdout.write(JSON.stringify(value));
});'''
    done = subprocess.run(
        [node, '-e', runner],
        input=build_panel_probe_js(SITES['zhaopin'], 1),
        text=True,
        capture_output=True,
        encoding='utf-8',
        check=True,
    )
    result = json.loads(done.stdout)
    assert result['target_card_found'] is True
    assert result['target_active'] is True
    assert result['panel_visible'] is True
    assert result['panel_title'] == '后端工程师'
    assert result['description'] == '负责服务开发'
    assert result['list_url'].startswith('https://www.zhaopin.com/jobs/')
