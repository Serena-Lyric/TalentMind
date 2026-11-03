"""Conservative source constraints; no skill dictionary, DEV IDs, or knowledge approval."""
from copy import deepcopy
import re
import unicodedata

from .core import locate

POLICY_VERSION = "p1-source-constraints-5"


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


def _section_positions(text,labels,*,whitespace_delimited=False):
    boundary=r'(?:^|[\r\n。；;！？!?])'
    positions=[match.start() for match in re.finditer(
        rf'{boundary}[ \t]*(?:{labels})',text,flags=re.MULTILINE)]
    if whitespace_delimited:
        positions.extend(match.start() for match in re.finditer(
            rf'(?<!\S)(?:{labels})(?=\s|[:：]|$)',text,flags=re.MULTILINE))
    return sorted(set(positions))


def _soft_section(text,start):
    prefix=text[:start]
    hard=_section_positions(
        prefix,
        r'硬性|任职要求|任职资格|职位要求|岗位要求|岗位职责|工作职责|'
        r'职位描述|招聘流程|申请|投递|联系方式|其他信息|工作地点')
    hard.extend(_section_positions(
        prefix,
        r'硬性|任职要求|任职资格|职位要求|岗位要求|岗位职责|工作职责|'
        r'职位描述|招聘流程|申请流程|投递方式|联系方式|其他信息|工作地点',
        whitespace_delimited=True))
    hard=sorted(set(hard))
    soft=_section_positions(
        prefix,r'期望(?:（[^）]*）|\([^)]*\))?|我们更看重')
    return bool(soft and (not hard or soft[-1]>hard[-1]))


def _scope_positions(req,record):
    return [locate(evidence,record) for evidence in req['scope_evidence']]


def _is_open_example_marker(member):
    value=_normal(member)
    return value=='等' or bool(re.fullmatch(
        r'等.{0,16}(?:工具|框架|语言|技术|协议|方法|产品|实践|能力|选项|方案|平台|系统)',
        value))


def apply_constraints(claims,record,inside):
    claims=deepcopy(claims);changes=[]
    for claim in claims:
        req=claim['requirement']
        if not req:continue
        scopes=_scope_positions(req,record)
        if req['state']=='required' and any(
                _soft_section(record.payload[e['field']],e['end']) for e in scopes):
            req['state']='preferred'
            req['reason']='来源位于“期望”或“更看重”软性章节，状态降为 preferred，不升级硬性门槛；原对象、组合、程度及证据保留。'
            claim['reason']=req['reason']
            changes.append(dict(rule='soft_section_not_required',claim_ids=[claim['id']],
                                before='required',after='preferred'))
        if req['open_set']:
            markers=[member for member in req['members'] if _is_open_example_marker(member)]
            if markers and len(markers)<len(req['members']):
                before=list(req['members'])
                req['members']=[member for member in req['members']
                                if not _is_open_example_marker(member)]
                req['reason']='开放集合标记由 open_set 表达，不把“等…”计作具名成员；保留全部原示例与未知范围。'
                claim['reason']=req['reason']
                changes.append(dict(rule='open_example_suffix_not_member',
                                    claim_ids=[claim['id']],before=before,
                                    after=list(req['members'])))
        # Normalize for semantic cue recognition only; locators retain original bytes/offsets.
        context=_local_quantifier_context(req,record)
        if (req['target']=='experience' and req['condition'] is not None
                and re.search(r'(?:投递|申请|提交)(?:时|阶段|前)',req['condition'])
                and re.search(r'(?:附上?|提供|提交|上传)',context)
                and re.search(r'作品集|项目链接|技术文章|GitHub|证明|材料',context,re.IGNORECASE)
                and not re.search(r'\d+\s*年|工作经历|实习经历|项目经验|从业经验|年限',context)):
            before=dict(target=req['target'],condition=req['condition'])
            req['target']='unresolved'
            req['condition']=None
            req['reason']='来源要求申请材料中的可验证产物，但现有目标枚举不能无歧义地归为能力或经验；目标有界保留为 unresolved，不把申请阶段误作资格条件。'
            claim['reason']=req['reason']
            changes.append(dict(rule='application_artifact_target_unresolved',
                                claim_ids=[claim['id']],before=before,
                                after=dict(target=req['target'],condition=req['condition'])))
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
    groups={}
    for claim in claims:
        req=claim['requirement']
        if not req or req['state']!='preferred':continue
        scopes=_scope_positions(req,record)
        if len(scopes)==1:
            e=scopes[0]
            groups.setdefault((e['field'],e['start'],e['end']),[]).append((claim,e))
    for group in groups.values():
        if len(group)<2:continue
        choices=[item for item in group if item[0]['requirement']['target']=='capability'
                 and item[0]['requirement']['combination'] in {'any_of','unresolved'}]
        outputs=[item for item in group if item[0]['requirement']['target']=='experience']
        for claim,scope in choices:
            req=claim['requirement']
            if req['condition'] is not None:continue
            source=record.payload[scope['field']][scope['start']:scope['end']]
            candidates=[]
            preference_scope=re.compile(r'优先|加分|更佳|最佳|最好|受青睐')
            for sentence in re.finditer(r'[^。；;\n]+',source):
                local=sentence.group()
                if not re.search(r'或|任选|任一|任意|至少',local):continue
                if not any(_normal(member) in _normal(local)
                           for member in req['members']):continue
                local_clauses=list(re.finditer(r'[^，,]+',local))
                choice_clauses=[clause for clause in local_clauses
                                if any(_normal(member) in _normal(clause.group())
                                       for member in req['members'])]
                for output,_ in outputs:
                    for member in output['requirement']['members']:
                        if len(_normal(member))>=2 and member in local:
                            condition_start=local.index(member)
                            before=re.split(r'[，,]',local[:condition_start])[-1]
                            after=re.split(r'[，,]',local[condition_start+len(member):])[0]
                            independent_priority=(
                                r'\s*(?:也|另|另外|此外|还|再)'
                                r'(?:\s*(?:优先|加分|更佳|最佳|最好))?\s*')
                            if (re.fullmatch(independent_priority,before)
                                    or re.fullmatch(independent_priority,after)):
                                continue
                            output_clause=next((clause for clause in local_clauses
                                                if clause.start()<=condition_start<clause.end()),None)
                            if (output_clause and any(preference_scope.search(clause.group())
                                                      for clause in choice_clauses)
                                    and preference_scope.search(output_clause.group())):
                                continue
                            candidates.append((len(member),member,sentence.start()))
            if not candidates:continue
            _,condition,sentence_start=max(candidates)
            condition_start=source.index(condition,sentence_start)
            locator=_loc(scope['field'],scope['start']+condition_start,
                         scope['start']+condition_start+len(condition),record)
            if locator not in req['scope_evidence']:req['scope_evidence'].append(locator)
            req['condition']=condition
            req['reason']='软性选择项与同一句的产出共同构成条件；任一框架选择保留，同时不丢失可运行产出要求。'
            claim['reason']=req['reason']
            changes.append(dict(rule='soft_choice_shared_output_condition',
                                claim_ids=[claim['id']],condition=condition))
    return claims,changes
