/** Pure functions used by the UI; independent of dataset or browser storage. */
export function filterSamples(samples, {query="", classKey="all", wrongOnly=false, minLoss=0, sort="loss"}={}) {
  const q=String(query).trim().toLocaleLowerCase("ja");
  const lowerBound=Number.isFinite(Number(minLoss)) ? Number(minLoss) : 0;
  const filtered=samples.filter(s=>
    (!q || [s.id,s.className,s.predictedClass,s.classKey].some(v=>String(v).toLocaleLowerCase("ja").includes(q))) &&
    (classKey==="all" || s.classKey===classKey) &&
    (!wrongOnly || !s.correct) &&
    s.loss>=lowerBound
  );
  filtered.sort((a,b)=> sort==="id" ? a.id-b.id : sort==="class" ? a.className.localeCompare(b.className,"ja") || a.id-b.id : b.loss-a.loss || a.id-b.id);
  return filtered;
}

function parseId(id) {
  if (typeof id !== "number" && !(typeof id === "string" && /^\d+$/.test(id.trim()))) {
    throw new TypeError("画像IDは0以上の整数で入力してください");
  }
  const value=Number(id);
  if (!Number.isSafeInteger(value) || value<0) throw new TypeError("画像IDは0以上の整数で入力してください");
  return value;
}

export function addPick(picks,id,max=10) {
  const idNum=parseId(id);
  if (picks.includes(idNum)) return [...picks];
  if (picks.length>=max) throw new RangeError(`最大${max}枚までです`);
  return [...picks,idNum];
}

export function togglePick(picks,id,max=10) {
  const idNum=parseId(id);
  if (picks.includes(idNum)) return picks.filter(x=>x!==idNum);
  if (picks.length>=max) throw new RangeError(`最大${max}枚までです`);
  return [...picks,idNum];
}

export function sanitizeSavedPicks(ids, validIds, max=10) {
  if (!Array.isArray(ids)) return [];
  const allowed=new Set(validIds);
  return [...new Set(ids.filter(id=>Number.isInteger(id) && allowed.has(id)))].slice(0,max);
}
