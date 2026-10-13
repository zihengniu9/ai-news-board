(()=>{
 'use strict';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const stamp=s=>s?new Date(s).toLocaleString('zh-CN',{timeZone:'Asia/Singapore',hour12:false}):'尚未采集';
 let data=window.MEDIA_DATA||{articles:[],sources:[]}, hours=168, selected=null, query='',onlyWatched=false,busy=false,token=null;
 let custom=[],watched=[];
 try{const s=JSON.parse(localStorage.getItem('media-monitor-v1')||'{}');custom=(s.custom||[]).filter(x=>typeof x.name==='string'&&Array.isArray(x.terms)&&x.terms.every(t=>typeof t==='string'));watched=Array.isArray(s.watched)?s.watched:[];}catch{}
 function save(){try{localStorage.setItem('media-monitor-v1',JSON.stringify({custom,watched}));}catch{message('浏览器未允许保存，关注仅在本次有效');}}
 function message(s){document.querySelector('#heatFeedback').textContent=s;}
 const summary=()=>HeatMath.summarize(data,[...HeatMath.defaults,...custom],hours);
 function chart(t){
  const max=Math.max(1,...t.trend.map(d=>d.count));
  return '<div class="heat-chart" role="img" aria-label="'+esc(t.name+'近7天已采集报道：'+t.trend.map(d=>new Date(d.start+8*3600000).toISOString().slice(5,10)+' '+d.count+'条').join('；'))+'">'+t.trend.map(d=>'<div class="heat-day"><b>'+d.count+'</b><div class="heat-track"><span style="height:'+Math.max(2,d.count/max*78)+'px"></span></div><small>'+new Date(d.start+8*3600000).toISOString().slice(5,10)+'</small></div>').join('')+'</div>';
 }
 function render(){
  const panel=document.querySelector('#heatPanel');if(!panel)return;
  let topics=summary();
  const matching=topics.filter(t=>(!query || (t.name+' '+t.terms.join(' ')).toLowerCase().includes(query.toLowerCase()))&&(!onlyWatched||watched.includes(t.id)));
  if(!matching.some(t=>t.id===selected))selected=matching[0]?.id;
  const active=matching.find(t=>t.id===selected),now=Date.now();
  const records=HeatMath.dedupe(data.articles).filter(a=>a.published>now-hours*3600000&&a.published<=now);
  const media=new Set(records.flatMap(a=>a.links.map(l=>l.sourceId)));
  const ok=data.sources.filter(s=>s.status==='ok').length;
  panel.innerHTML='<div class="heat-intro"><div><span class="eyebrow">MEDIA ATTENTION</span><h2>哪些 AI 话题，媒体正在讨论？</h2><p>从报道中发现选题，再回原文判断价值。</p></div>'+(location.protocol==='https:'?'':'<button class="button secondary" id="heatRefresh" '+(busy?'disabled':'')+'>'+(busy?'正在采集…':'刷新媒体报道')+'</button>')+'</div>'+
   '<div class="heat-status">'+ok+' / '+data.sources.length+' 个媒体源可用 · 最近采集 '+esc(stamp(data.snapshot))+'（新加坡） · '+(data.scheduled?'每 4 小时自动采集':'手动刷新')+'</div><p id="heatFeedback" role="status"></p>'+
   '<div class="heat-stats">'+[['去重报道',records.length,'当前所选时间范围'],['覆盖媒体',media.size,'媒体数，不是转载次数'],['有报道的话题',topics.filter(t=>t.count).length,'按标题关键词归类'],['热度变化',data.comparisonReady?'可比较':'积累中','需要连续、同源的历史样本']].map(([a,b,c])=>'<article><span>'+a+'</span><strong>'+b+'</strong><small>'+c+'</small></article>').join('')+'</div>'+
   '<div class="heat-controls"><div class="heat-period"><button data-heat-hours="24" aria-pressed="'+(hours===24)+'">近 24 小时</button><button data-heat-hours="168" aria-pressed="'+(hours===168)+'">近 7 天</button></div><label class="heat-watch-filter"><input id="heatOnlyWatched" type="checkbox" '+(onlyWatched?'checked':'')+'>只看关注</label><input id="heatSearch" type="search" aria-label="搜索监控话题" placeholder="查找话题或关键词" value="'+esc(query)+'"></div>'+
   '<div class="heat-layout"><div><div class="heat-ranking"><div class="heat-table-head"><span>话题 · 点击展开</span><span>报道</span><span>媒体</span></div>'+matching.map((t,i)=>'<button class="heat-topic '+(t.id===selected?'selected':'')+'" data-heat-topic="'+esc(t.id)+'" aria-pressed="'+(t.id===selected)+'"><span class="heat-topic-name"><small>'+String(i+1).padStart(2,'0')+'</small><span><strong>'+esc(t.name)+(watched.includes(t.id)?' <i>已关注</i>':'')+'</strong><span class="heat-bar"><b style="width:'+(t.count?Math.max(3,t.count/Math.max(...topics.map(x=>x.count),1)*100):0)+'%"></b></span></span></span><b>'+t.count+'</b><span>'+t.media.length+'</span></button>').join('')+(!matching.length?'<p class="heat-empty">没有符合条件的话题，可以添加关键词关注。</p>':'')+'</div>'+
   '<form id="heatAdd" class="heat-add"><h3>添加关注话题</h3><p>填写名称和标题关键词，多个关键词用逗号分隔。</p><label>话题名称<input name="name" required maxlength="40" placeholder="例如：科研 AI"></label><label>匹配关键词<input name="terms" required maxlength="300" placeholder="例如：AI论文, literature review, AI research"></label><button class="button primary" type="submit">添加并关注</button></form></div><aside class="heat-detail">'+(active?detail(active):'<p>选择话题查看报道。</p>')+'</aside></div>'+
   '<details class="heat-method"><summary>统计口径与媒体源状态</summary><p>当前展示公开 RSS / Atom 订阅中抓到的样本，不代表全网报道、阅读量或社交讨论量。话题按标题关键词匹配，可能交叉归类；话题数不能相加作为总报道量。</p><p>相同规范化标题合为一组，并保留所有来源链接；这只是疑似重复合并，不代表已确认转载关系。未标注日期的记录不计入时间窗。7 天分布按新加坡自然日计数，今天尚未结束；RSS 的历史覆盖可能不完整，0 表示未采集到。</p><p>24 小时变化只在连续 48 小时有同源记录、采集间隔不超过 6 小时且最新采集未超过 6 小时时展示。它表示已采集报道的变化，不是全网增长率。失败来源保留旧记录并标记。</p>'+data.sources.map(s=>'<div class="heat-source"><a href="'+esc(s.url)+'" target="_blank" rel="noopener noreferrer">'+esc(s.name)+'</a><span>'+ (s.status==='ok'?'读取成功 · '+s.parsed+' 条':s.status==='disabled'?'已停用':'读取失败')+'</span><small>'+esc(s.error||'最近读取：'+stamp(s.checkedAt))+'</small></div>').join('')+'</details>';
 }
 function detail(t){
  const delta=t.delta ? (t.delta.previous===0?'上期 0 条，本期 '+t.delta.current+' 条':(t.delta.difference>=0?'+':'')+t.delta.difference+' 条（'+t.delta.percent+'%）'):'历史样本积累中';
  return '<div class="eyebrow">TOPIC NOTE</div><h2>'+esc(t.name)+'</h2><div class="heat-actions"><button class="button secondary" data-watch="'+esc(t.id)+'">'+(watched.includes(t.id)?'取消关注':'关注话题')+'</button><button class="button primary" data-heat-save="'+esc(t.id)+'">加入选题</button></div><p class="heat-match">标题匹配：'+esc(t.terms.join(' / '))+'</p>'+chart(t)+'<p class="heat-chart-note">近 7 个自然日的已采集报道 · 今天未结束</p><div class="heat-delta">24 小时变化：'+(hours===24?esc(delta):'切换到近 24 小时查看')+'</div><h3>相关报道 <small>'+t.count+' 组 / '+t.media.length+' 家媒体</small></h3>'+t.reports.map(a=>'<article class="heat-article"><strong>'+esc(a.title)+'</strong><small>'+esc(stamp(a.date))+(a.links.some(l=>l.stale)?' · 含上次成功记录':'')+'</small><div>'+a.links.map(l=>'<a href="'+esc(l.url)+'" target="_blank" rel="noopener noreferrer">'+esc(l.brand)+' ↗</a>').join('')+'</div></article>').join('')+(!t.count?'<p class="heat-empty">所选时间内暂无匹配报道。这里的 0 不代表全网没人讨论。</p>':'')+(t.unknown?'<p>'+t.unknown+' 条无发布时间，未计入热度。</p>':'');
 }
 async function read(){
  const r=await fetch('/api/media',{cache:'no-store'});if(!r.ok)throw new Error('媒体服务暂不可用，保留上次快照');
  const result=await r.json();data=result;window.MEDIA_DATA=result;token=result.token;render();window.dispatchEvent(new Event('media-updated'));return result;
 }
 async function refresh(){
  if(location.protocol==='file:')return message('请通过 http://127.0.0.1:8766/ 打开看板后刷新。');
  try{
   if(!token)await read();
   const r=await fetch('/api/media/refresh',{method:'POST',headers:{'X-Board-Token':token}}),j=await r.json();
   if(!r.ok)throw new Error(j.error||'刷新失败');busy=true;render();
   while(busy){await new Promise(resolve=>setTimeout(resolve,1500));const response=await fetch('/api/status',{cache:'no-store'});if(!response.ok)throw new Error('无法读取采集状态');const status=await response.json();if(!status.running){busy=false;await read();message(status.lastError||'本轮采集完成，来源状态见下方。');}}
  }catch(e){busy=false;render();message(e.message);}
 }
 document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.id==='heatRefresh')refresh();
  if(b.dataset.heatHours){hours=Number(b.dataset.heatHours);render();}
  if(b.dataset.heatTopic){selected=b.dataset.heatTopic;render();}
  if(b.dataset.watch){const id=b.dataset.watch;watched=watched.includes(id)?watched.filter(v=>v!==id):[...watched,id];save();render();}
  if(b.dataset.heatSave){
   const t=summary().find(t=>t.id===b.dataset.heatSave);
   window.saveHeatTopic?.({id:'media-'+t.id,title:'媒体观察：'+t.name,brand:'媒体话题监控',type:'release',category:'媒体观察',date:null,dateLabel:stamp(data.snapshot)+' 采集快照',summary:'近 '+(hours===24?'24 小时':'7 天')+'采集到 '+t.count+' 组报道，覆盖 '+t.media.length+' 家媒体。',tags:['媒体样本','需核对一手来源'],facts:['标题关键词：'+t.terms.join(' / '),'统计仅覆盖已接入媒体，不能代表全网热度。'],conditions:['媒体报道中的事实应回到官方或原始材料核对。'],sources:t.reports.flatMap(a=>a.links.map(l=>({label:l.brand+'：'+l.title,url:l.url}))),angle:'从读者的具体问题切入，避免只复述新闻。',format:'话题解读 / 实用教程',audience:'待确定',priority:99,savedArchive:true,lastChecked:data.snapshot,checked:'保存时的报道快照'});
  }
 });
 document.addEventListener('input',e=>{if(e.target.id==='heatSearch'){const pos=e.target.selectionStart;query=e.target.value;render();const field=document.querySelector('#heatSearch');field.focus();try{field.setSelectionRange(pos,pos);}catch{}}});
 document.addEventListener('change',e=>{if(e.target.id==='heatOnlyWatched'){onlyWatched=e.target.checked;render();}});
 document.addEventListener('submit',e=>{
  if(e.target.id!=='heatAdd')return;e.preventDefault();const f=new FormData(e.target),name=String(f.get('name')).trim(),terms=[...new Set(String(f.get('terms')).split(/[,，、\n]/).map(s=>s.trim()).filter(Boolean))];
  if(!name||!terms.length||terms.length>10)return message('请填写名称和 1–10 个关键词。');
  if(custom.length>=30)return message('已达到 30 个自定义话题上限。');
  const id='custom-'+Date.now();custom.push({id,name,terms});watched.push(id);selected=id;query='';save();render();message('已开始关注：'+name);
 });
 window.renderHeat=render;
 document.addEventListener('DOMContentLoaded',()=>{render();if(location.protocol==='http:')read().catch(e=>message(e.message));});
})();
