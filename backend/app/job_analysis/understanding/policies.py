"""Conservative source constraints; no skill dictionary, DEV IDs, or knowledge approval."""
from copy import deepcopy
import re
import unicodedata

from .core import locate

POLICY_VERSION = "p1-source-constraints-1"


def _normal(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()


def _loc(field, start, end, record):
    text=record.payload[field];quote=text[start:end];positions=[];at=0
    while (found:=text.find(quote,at))>=0:
        positions.append(found);at=found+1
    return dict(field=field,quote=quote,occurrence=positions.index(start) if len(positions)>1 else None)


def _member_anchor(member):
    value=_normal(member)
    value=re.sub(r'^(?:完整的?|良好的?|较强的?|较好的?|一定的?|丰富的?)','',value)
    value=re.sub(r'从?\d+.*(?:经验|能力)$','',value)
    value=re.sub(r'(?:项目)?(?:经验|能力)$','',value)
    value=re.sub(r'项目$','',value)
    return value or _normal(member)


def _local_quantifier_context(req,record):
    """Return source clauses containing every member, including split citations."""
    spans={}
    for evidence in req['scope_evidence']:
        grounded=locate(evidence,record)
        lo,hi=grounded['start'],grounded['end']
        field=grounded['field']
        if field in spans:spans[field]=[min(lo,spans[field][0]),max(hi,spans[field][1])]
        else:spans[field]=[lo,hi]
    clauses=[]
    for field,(lo,hi) in spans.items():
        text=unicodedata.normalize('NFKC',record.payload[field][lo:hi])
        for sentence in re.split(r'[。；;\n]+',text):
            parts=re.split(r'[，,]+',sentence)
            windows=[]
            for start in range(len(parts)):
                for end in range(start,len(parts)):
                    clause='，'.join(parts[start:end+1])
                    normalized=_normal(clause)
                    if all(_member_anchor(member) in normalized for member in req['members']):
                        windows.append((end-start,start,end,clause))
            if not windows:continue
            _,start,end,clause=min(windows)
            quantifier_only=r'\s*(?:任选|任一|任意|之一|至少.{0,8}(?:一种|一项|一门|一个))\s*'
            if start>0 and re.fullmatch(quantifier_only,_normal(parts[start-1])):
                clause=parts[start-1]+'，'+clause
            if end+1<len(parts) and re.fullmatch(quantifier_only,_normal(parts[end+1])):
                clause=clause+'，'+parts[end+1]
            clauses.append(clause.strip())
    return '\n'.join(dict.fromkeys(clauses))


def apply_constraints(claims,record,inside):
    claims=deepcopy(claims);changes=[]
    for claim in claims:
        req=claim['requirement']
        if not req:continue
        # Normalize for semantic cue recognition only; locators retain original bytes/offsets.
        context=_local_quantifier_context(req,record)
        if req['target']=='capability' and req['combination']=='single' and all(re.search(r'(?:习惯|态度)$',m) for m in req['members']):
            if req['category']!='soft_skill':
                changes.append(dict(rule='disposition_not_execution_method',claim_ids=[claim['id']],before=req['category'],after='soft_skill'))
                req['category']='soft_skill'
                req['reason']='陈述表达习惯/态度倾向，归软技能；原状态、程度与作用域保留，不解释成具体工程执行方法。'
                claim['reason']=req['reason']
        negative_quantifier=bool(re.search(
            r'(?:不要求|无需|无须|不必|并非|不是)[^。；;\n]{0,12}'
            r'(?:全部|所有|每项|都需|均需|都|均)',context)
            or re.search(r'(?:全部|所有|每项|都需|均需)[^。；;\n]{0,12}'
                         r'(?:不必|无需|不要求|并非|不是)',context))
        choice_marker=r'或|任选|任一|任意|之一|至少.{0,8}(?:一种|一项|一门|一个)'
        explicit_choice=(bool(re.search(choice_marker,context))
                         and not bool(re.search(r'(?:不要求|无需|无须|不必|并非|不是)[^。；;\n]{0,16}'
                                               rf'(?:{choice_marker})',context))
                         and not bool(re.search(rf'(?:{choice_marker})[^。；;\n]{{0,20}}'
                                               r'(?:不要求|无需|无须|不必|并非|不是|都不|均不|全不)',context)))
        education_choice=False
        if req['target']=='education':
            for part in re.findall(r'[^，,。；;\n]+相关专业',context):
                if len(req['members'])>1 and all(_normal(m) in _normal(part) for m in req['members']):
                    education_choice=True
        examples=req['open_set'] and bool(re.search(r'如|例如|比如|等(?:工具|语言|框架|技术|协议|方法|能力|产品|实践|[，,。；;）)]|$)',context))
        all_explicit=(bool(re.search(r'缺一不可|全部|所有|每项|都需|均需|全部满足',context))
                      and not negative_quantifier)
        if ((req['combination']=='any_of' and not explicit_choice and not education_choice)
                or (req['combination']=='all_of'
                    and (negative_quantifier or (examples and not all_explicit)))):
            before=req['combination'];req['combination']='unresolved'
            req['reason']='来源的列举/开放示例未给出所提量词，组合保留未定；原选项、状态及程度完整保留。'
            claim['reason']=req['reason']
            eligible=[e['quote'] for e in req['scope_evidence'] if all(_normal(m) in _normal(e['quote']) for m in req['members'])]
            if eligible:claim['text']=min(eligible,key=len)
            changes.append(dict(rule='no_invented_enumeration_quantifier',claim_ids=[claim['id']],before=before,after='unresolved'))
        filters={}
        for ev in req['scope_evidence']:
            grounded=locate(ev,record)
            for field in re.finditer(r'(行业|语言)要求\s*[：:]\s*((?:(?!(?:行业|语言)要求\s*[：:])[^。；;\n])+)',grounded['quote']):
                value=field.group(2).strip();actual=field.group().strip()
                if not value or not any(_normal(m) in _normal(actual) or _normal(value) in _normal(m) for m in req['members']):continue
                if field.group(1)=='语言' and value not in {'不限','未知','未说明','未明确'}:continue
                prefix=record.payload[grounded['field']][:grounded['start']+field.start()]
                header=list(re.finditer(r'其他信息|任职要求|任职资格|岗位职责|工作职责|公司简介',prefix))
                if (header and header[-1].group()=='其他信息'
                        and not re.search(r'经验|背景|从业|年|必须|需要|证书|资格|至少|熟悉|掌握|优先|加分|必备|可选|仅限|须|级',value)):
                    filters[(grounded['field'],grounded['start']+field.start())]=actual
        if len(filters)==1 and (req['state'],req['target'])!=('uncertain','unresolved'):
            changes.append(dict(rule='platform_filter_eligibility_unknown',claim_ids=[claim['id']],before=[req['state'],req['target']],after=['uncertain','unresolved']))
            req.update(state='uncertain',target='unresolved',category=None)
            req['reason']='来源分类/筛选值已保留，但它限制候选人哪类资格尚未明确；不解释为必备行业经验或背景不限。'
            claim.update(reason=req['reason'],text=next(iter(filters.values())))
    # Do not turn an incomplete nominal possession into two independently required
    # capabilities. Preserve the exact unresolved source expression instead.
    mixed=re.compile(r'(?:具备|有)(?:良好|较强|较好|一定|丰富)?的?([^，,。；;：:\n]{1,30}(?:模式|框架|工具|系统|平台|协议|模型))(?:及|和|与)([^，,。；;：:\n]{1,25}能力)')
    handled=set()
    for field in ('raw_text','duties','requirements','experience'):
        text=record.payload.get(field,'')
        for match in mixed.finditer(text):
            paragraph=re.split(r'[。；;\n]',text[:match.start()])[-1]+text[match.start():re.search(r'[。；;\n]',text[match.end():]).start()+match.end() if re.search(r'[。；;\n]',text[match.end():]) else len(text)]
            if re.search(r'必须|全部|同时|缺一不可|两项|两者|均需|都需',paragraph):continue
            ref=_loc(field,match.start(),match.end(),record);source=locate(ref,record)
            chosen=[];arms=[False,False]
            for c in claims:
                q=c['requirement']
                if (not q or c['id'] in handled or q['condition'] is not None
                        or q['degree_polarity']=='negated' or q['state'] not in {'required','preferred','uncertain'}):continue
                evidence=[locate(e,record) for e in c['evidence']+q['scope_evidence']]
                if not (inside(source,evidence,record) or any(inside(e,[source],record) for e in evidence)):continue
                found=[any(_normal(m) in _normal(arm) or _normal(arm) in _normal(m) for m in q['members']) for arm in match.groups()]
                if any(found):
                    chosen.append(c);arms=[a or b for a,b in zip(arms,found)]
            if not chosen or not all(arms):continue
            states={c['requirement']['state'] for c in chosen}
            targets={c['requirement']['target'] for c in chosen}
            categories={c['requirement']['category'] for c in chosen}
            state=next(iter(states)) if len(states)==1 else 'uncertain'
            target='capability' if targets=={'capability'} else 'unresolved'
            category=next(iter(categories)) if target=='capability' and len(categories)==1 else None
            modifier=re.match(r'(?:具备|有)(良好|较强|较好|一定|丰富)的?',match.group())
            degree=modifier.group(1) if modifier else None
            why='保留整体能力要求及原状态/程度；技术概念名词与能力混合并列的内部组合未明，不分配成两个独立必备门槛。'
            for c in chosen:
                c.update(text=match.group(),reason=why,core=None,evidence=[ref])
                c['requirement']=dict(state=state,target=target,category=category,members=list(match.groups()),
                    combination='unresolved',open_set=False,degree=degree,degree_polarity='affirmed' if degree else None,
                    condition=None,reason=why,scope_evidence=[ref])
                handled.add(c['id'])
            changes.append(dict(rule='mixed_nominal_capability_not_independent_mandates',claim_ids=[c['id'] for c in chosen],source=source,
                                after=dict(state=state,target=target,degree=degree,combination='unresolved')))
    return claims,changes
