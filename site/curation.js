(function (root) {
  'use strict';
  // A watchlist, not a claim about company popularity or a full-market ranking.
  const companies = [
    {id:'openai',name:'OpenAI',terms:['OpenAI','ChatGPT','Codex','GPT'],sources:['openai']},
    {id:'google',name:'Google',terms:['Google','谷歌','Gemini','DeepMind','NotebookLM','Veo'],sources:['google']},
    {id:'anthropic',name:'Anthropic',terms:['Anthropic','Claude'],sources:['anthropic']},
    {id:'microsoft',name:'微软 / GitHub',terms:['Microsoft','微软','GitHub','Copilot'],sources:['github']},
    {id:'cursor',name:'Cursor',terms:['Cursor','Anysphere'],sources:['cursor']},
    {id:'deepseek',name:'DeepSeek',terms:['DeepSeek','深度求索'],sources:[]},
    {id:'alibaba',name:'阿里 / Qwen',terms:['Alibaba','阿里','Qwen','通义','千问'],sources:[]},
    {id:'bytedance',name:'字节 / 豆包',terms:['ByteDance','字节','豆包','Seedance','Seedream'],sources:[]},
    {id:'moonshot',name:'月之暗面 / Kimi',terms:['Moonshot AI','月之暗面','Kimi'],sources:[]},
    {id:'zhipu',name:'智谱',terms:['智谱','Zhipu','GLM','智聊'],sources:[]},
    {id:'minimax',name:'MiniMax',terms:['MiniMax','海螺'],sources:[]},
    {id:'meta',name:'Meta',terms:['Meta AI','Meta','Llama'],sources:[]},
    {id:'xai',name:'xAI',terms:['xAI','Grok'],sources:[]},
    {id:'nvidia',name:'NVIDIA',terms:['NVIDIA','英伟达','Nemotron'],sources:[]},
    {id:'huggingface',name:'Hugging Face',terms:['Hugging Face','HuggingFace'],sources:['huggingface']},
    {id:'mistral',name:'Mistral',terms:['Mistral','Le Chat'],sources:[]}
  ];
  const kinds = {feature:'新功能',model:'模型发布',event:'可参与活动'};
  const defaults = () => ({followed:companies.slice(0,11).map(c=>c.id),hidden:[],kept:[],keywords:[],smart:true});
  function normalize(raw) {
    const p=defaults();
    if (!raw || typeof raw!=='object') return p;
    for(const key of ['followed','hidden','kept','keywords']) if(Array.isArray(raw[key])) p[key]=[...new Set(raw[key].filter(s=>typeof s==='string'&&s.length<=300))];
    p.followed=p.followed.filter(id=>companies.some(c=>c.id===id));
    p.keywords=p.keywords.map(s=>s.trim()).filter(Boolean).slice(0,50);
    if(typeof raw.smart==='boolean')p.smart=raw.smart;
    return p;
  }
  function matches(text, term) {
    const literal=term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
    return new RegExp((/^[a-z0-9]/i.test(term)?'(?<![a-z0-9])':'')+literal+(/[a-z0-9]$/i.test(term)?'(?![a-z0-9])':''),'i').test(text);
  }
  function companyIds(item) {
    // Do not use sources[].labels, boilerplate conditions, or editorial angles as evidence.
    const title=String(item.title||'');
    return companies.filter(c=>(c.id!=='huggingface'&&c.sources.includes(item.sourceId))||c.terms.some(t=>matches(title,t)||(['Qwen','Llama','GLM','GPT'].includes(t)&&new RegExp('\\b'+t+'\\d','i').test(title)))).map(c=>c.id);
  }
  const launch=/\b(introducing|introduces?|launch(?:es|ed|ing)?|releases?|released|roll(?:ing|s)? out|now available|available now|debuts?|unveils?|adds?|added|new|upgrade[sd]?|updates?)\b|发布|上线|推出|上新|开放|新增|升级|更新|开源|公测|内测|支持了|现已|正式支持/i;
  const feature=/\b(apps?|tools?|features?|support|agent|agents|assistant|chat|search|video|image|voice|audio|coding|code|editor|browser|plugin|extension|api|workspace|integration|memory|skills?|workflow|game|platform|try.on|AI)\b|功能|工具|应用|试穿|换装|搜索|语音|图像|视频|智能体|助手|插件|编程|工作流|记忆|生成|上传|导入|导出|集成|游戏|平台/i;
  const model=/\b(model|models|GPT(?:[- ]?\d)|Claude|Gemini|Llama|Qwen|DeepSeek|GLM|Mistral|Nemotron|Veo|Sora)\b|模型|大模型/i;
  const noise=/\b(fundrais(?:e|ing)|funding round|raises? \$|valuation|acqui(?:res?|sition)|appoints?|hiring|careers?|earnings|sponsorship|partnership|partners with|joins? (?:our|the) (?:team|board)|customer stor(?:y|ies))\b|融资|估值|收购|任命|招聘|财报|合作伙伴|战略合作|客户案例|品牌宣传/i;
  const commentary=/\b(opinion|insights|rumou?rs?|reportedly|could launch|may launch|plans to|expected to|how to|guide to|tutorial|our vision|upgrade operations)\b|传闻|据传|有望|计划推出|预计发布|观点|专访|使用教程|使用指南|如何使用/i;
  const price=/\b(pric(?:e|es|ing)|discount|cheaper|subscription|credits?)\b|调价|降价|涨价|订阅价格|免费额度|价格调整/i;
  const actionEvent=/\b(register|registration|sign.up|apply|applications|join us|hackathon|hack week|challenge|workshop|webinar)\b|报名|参赛|挑战赛|黑客松|训练营|申请参与|兑换|领券/i;
  function classify(item, now=Date.now()) {
    const title=String(item.title||'');
    const summary=String(item.summary||'');
    const all=title+' '+summary;
    if(item.type==='event') {
      if(item.end&&Date.parse(item.end)<now)return {kind:null,reason:'活动已结束'};
      if(actionEvent.test(all)||/^mlh/.test(item.sourceId||''))return {kind:'event',reason:'活动线索 · 参与资格仍需核对'};
      return {kind:null,reason:'未识别到可参与的活动入口'};
    }
    if(/\b(chips?|GPUs?|data cent(?:er|re)s?)\b|芯片|数据中心|算力中心/i.test(title)&&!(/\b(app|tool|feature|software|model)\b|功能|工具|软件|模型/i.test(title)))return {kind:null,reason:'硬件或基础设施消息'};
    if(commentary.test(title))return {kind:null,reason:'观点、教程或未确认的发布消息'};
    const launched=launch.test(title);
    // Strong headline exclusion; a generic AI/model mention in a summary is not a release.
    if(noise.test(title)&&!(/发布|推出|上线|introducing|launch|release|unveil/i.test(title)&&feature.test(title)))return {kind:null,reason:'企业、人事或商业宣传消息'};
    const priceOnly=price.test(title)&&!(/\b(adds?|added|supports?|features?|capabilit(?:y|ies))\b|新增|支持|能力|功能/i.test(title));
    if(priceOnly)return {kind:null,reason:'单纯价格或额度变化'};
    const modelVersion=/\b(?:GPT|Claude(?:\s+(?:Haiku|Sonnet|Opus))?|Gemini|Llama|Qwen|DeepSeek|GLM|Mistral|Veo|Sora)[-\s]*\d/i.test(title);
    if(launched&&model.test(title)&&(/\bmodels?\b|模型/.test(title.toLowerCase())||modelVersion)&&!(/\b(adds?|added|feature|support)\b|新增|功能|支持/.test(title.toLowerCase())))return {kind:'model',reason:'标题含模型发布或更新信号'};
    if(launched&&feature.test(title))return {kind:'feature',reason:'标题含产品新功能信号'};
    // Changelog titles can be short: use the actual release excerpt only for that source.
    if(item.sourceId==='cursor'&&feature.test(all)&&!noise.test(title)&&!price.test(title))return {kind:'feature',reason:'产品更新日志中的功能变更'};
    if(actionEvent.test(title)&&/报名|register|sign.up|applications open|join us|兑换/i.test(all))return {kind:'event',reason:'活动报名线索 · 资格与期限待核对'};
    return {kind:null,reason:'未识别到新功能、模型发布或可参与活动'};
  }
  function decision(item,prefs=defaults(),now=Date.now()) {
    const classification=classify(item,now);
    if(prefs.hidden.includes(item.id))return {...classification,hidden:true,reason:'你已手动隐藏'};
    if(prefs.kept.includes(item.id))return {...classification,hidden:false,reason:'你已恢复保留'};
    const keyword=prefs.keywords.find(k=>(String(item.title||'')+' '+String(item.summary||'')).toLocaleLowerCase().includes(k.toLocaleLowerCase()));
    if(keyword)return {...classification,hidden:true,reason:'屏蔽关键词：'+keyword};
    return {...classification,hidden:prefs.smart&&!classification.kind};
  }
  function canonical(url) {
    try {const u=new URL(url);u.hash='';for(const k of [...u.searchParams.keys()])if(/^utm_|^(fbclid|gclid)$/i.test(k))u.searchParams.delete(k);return u.href.replace(/\/$/,'');}catch{return String(url||'');}
  }
  function unique(items) {
    const seen=new Set();return items.filter(item=>{const key=canonical(item.url)||item.id;if(seen.has(key))return false;seen.add(key);return true;});
  }
  function recent(items, now=Date.now(), days=7) {
    return unique(items).filter(i=>i.date&&Number.isFinite(Date.parse(i.date))&&Date.parse(i.date)<=now&&Date.parse(i.date)>now-days*86400000);
  }
  const api={companies,kinds,defaults,normalize,matches,companyIds,classify,decision,unique,recent};
  if(typeof module!=='undefined')module.exports=api;else root.BoardCuration=api;
})(typeof window!=='undefined'?window:globalThis);
