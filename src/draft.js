import {sanitizeSavedPicks} from "./selection.js";
const KEY="tdm-demo-picks-v1";

/** A local draft is not a server vote. Corrupt or blocked storage is recoverable. */
export function loadDraft(storage,validIds) {
  try {
    const raw=JSON.parse(storage.getItem(KEY)||"{}");
    return {
      picks:sanitizeSavedPicks(raw?.picks,validIds),
      reason:typeof raw?.reason==="string"?raw.reason.slice(0,400):""
    };
  } catch { return {picks:[],reason:""}; }
}

export function saveDraft(storage,picks,reason) {
  try {
    storage.setItem(KEY,JSON.stringify({picks,reason:String(reason).slice(0,400)}));
    return true;
  } catch { return false; }
}
