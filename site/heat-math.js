(function(root){
 'use strict';
 const DAY=86400000;
 const defaults=[
  {id:'meta',name:'Meta 新模型',terms:['Meta','Muse Wonder','Llama']},
  {id:'safety',name:'AI 安全与监管',terms:['AI regulation','AI models need','AI models are','internal eval','AI gave','AI model sent','AI安全','AI监管','模型安全']},
  {id:'agents',name:'AI Agent 与自动化',terms:['AI agent','AI agents','智能体','Harness','DeepSeek Bot']},
  {id:'research',name:'AI 科研与论文',terms:['AI论文','mathematic','OpenAI’s latest drop','AI research','AI科研']},
  {id:'openai',name:'OpenAI / ChatGPT',terms:['OpenAI','ChatGPT','GPT-4o','GPT-6','Codex']},
  {id:'anthropic',name:'Anthropic / Claude',terms:['Anthropic','Claude']},
  {id:'local',name:'国产模型与应用',terms:['DeepSeek','智谱','华为AI','Qwen','通义','豆包','Kimi']},
  {id:'compute',name:'AI 芯片与算力',terms:['AI chip','Nvidia','GPU','data center','算力']},
  {id:'voice',name:'语音 AI',terms:['voice AI','AI app that listens','语音AI','语音 AI']},
  {id:'privacy',name:'AI 隐私与版权',terms:['AI agent makers','copyright','AI privacy','AI版权','AI隐私']}
 ];
 function matches(text,term){
  const escaped=term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  return new RegExp((/^[a-z0-9]/i.test(term)?'(?<![a-z0-9])':'')+escaped+(/[a-z0-9]$/i.test(term)?'(?![a-z0-9])':''),'i').test(text);
 }
 function dedupe(articles){
  const groups=new Map();
  for(const a of articles){
   const title=a.title.normalize('NFKC').toLocaleLowerCase().replace(/[\p{P}\p{Z}\s]+/gu,'');
   const key=title || a.url;
   if(!groups.has(key))groups.set(key,{...a,links:[],published:a.date?Date.parse(a.date):NaN});
   const g=groups.get(key);
   if(!g.links.some(l=>l.url===a.url))g.links.push(a);
   if(a.date && (!Number.isFinite(g.published)||Date.parse(a.date)<g.published))g.published=Date.parse(a.date);
  }
  return [...groups.values()];
 }
 function summarize(data,topics=defaults,hours=168,now=Date.now()){
  const groups=dedupe(data.articles || []), days=[];
  const today=Math.floor((now+8*3600000)/DAY)*DAY-8*3600000;
  for(let i=6;i>=0;i--)days.push(today-i*DAY);
  const results=topics.map(topic=>{
   // Title matching keeps grouping explainable; summaries do not imply central topic.
   const all=groups.filter(a=>topic.terms.some(term=>matches(a.title,term)));
   const inWindow=a=>Number.isFinite(a.published)&&a.published<=now&&a.published>now-hours*3600000;
   const reports=all.filter(inWindow).sort((a,b)=>b.published-a.published);
   const media=[...new Set(reports.flatMap(a=>a.links.map(l=>l.brand)))];
   const trend=days.map(start=>({start,count:all.filter(a=>a.published>=start&&a.published<Math.min(start+DAY,now+1)).length}));
   let delta=null;
   if(data.comparisonReady && hours===24 && now-Date.parse(data.snapshot)<6*3600000){
    const comparable=all.filter(a=>a.links.some(l=>data.comparisonSources.includes(l.sourceId)));
    const current=comparable.filter(inWindow).length;
    const previous=comparable.filter(a=>a.published>now-48*3600000&&a.published<=now-24*3600000).length;
    delta={current,previous,difference:current-previous,percent:previous?Math.round((current-previous)/previous*100):null};
   }
   return {...topic,reports,count:reports.length,media,trend,delta,unknown:all.filter(a=>!Number.isFinite(a.published)).length};
  });
  return results.sort((a,b)=>b.count-a.count||b.media.length-a.media.length||a.name.localeCompare(b.name));
 }
 const api={defaults,matches,dedupe,summarize};if(typeof module!=='undefined')module.exports=api;else root.HeatMath=api;
})(typeof window!=='undefined'?window:globalThis);
