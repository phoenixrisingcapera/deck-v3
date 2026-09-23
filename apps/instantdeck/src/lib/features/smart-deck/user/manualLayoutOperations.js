/** @param {{elements:Array<{id:string,x:number,y:number,width:number,height:number}>}|null} baseSchema @param {Array<{persistedElementId:string,elementKey:string,x:number,y:number,width:number,height:number}>} drafts */
export function buildManualLayoutOperations(baseSchema, drafts) {
  if (!baseSchema) return [];
  return drafts.flatMap((draft) => {
    const base = baseSchema.elements.find((element) => element.id === draft.elementKey);
    if (!base) return [];
    const operations = [];
    if (base.x !== draft.x || base.y !== draft.y) operations.push({ operation: 'move', persistedElementId: draft.persistedElementId, elementKey: draft.elementKey, x: draft.x, y: draft.y });
    if (base.width !== draft.width || base.height !== draft.height) operations.push({ operation: 'resize', persistedElementId: draft.persistedElementId, elementKey: draft.elementKey, width: draft.width, height: draft.height });
    return operations;
  });
}
/** @param {{identity:string,message:string}|null} notice @param {string} identity */
export function retainManualEditSuccessNotice(notice, identity) { return notice?.identity === identity ? notice : null; }
