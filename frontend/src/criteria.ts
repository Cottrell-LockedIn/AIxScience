export type Criterion = {id:string;label:string;min:number;max:number;unit:string;enabled:boolean;scale:number;domain:[number,number];step:number;help:string};
export const defaultCriteria:Criterion[] = [
['F01','Dark-area share',5,80,'%',100,0,100,1,'Sensitive to image segmentation'],
['F02','Bright-area share',0,60,'%',100,0,100,1,'Sensitive to image segmentation'],
['F03','Typical bright-object size',5,1200,'px',1,0,2000,1,'Sensitive to image segmentation'],
['F04','Larger bright-object size',5,2000,'px',1,0,3000,1,'Sensitive to image segmentation'],
['F05','Bright-object count',0,30000,'per Mpx',1,0,50000,100,'Sensitive to image segmentation'],
['F06','Bright-object clustering',0,3,'ratio',1,0,5,0.01,'Sensitive to image segmentation'],
['F07','Bright-object shape fullness',0,1,'ratio',1,0,1,0.01,'Sensitive to image segmentation'],
['F08','Typical width of dark regions',2,1200,'px',1,0,2000,1,'Needs further checking'],
['F09','Dark-region length ratio',0.1,10,'ratio',1,0.1,10,0.1,'Needs further checking'],
['F10','Variation in dark-area coverage',0,100,'pp',100,0,100,1,'Needs further checking'],
['F11','Bright boundary touching dark regions',0,100,'%',100,0,100,1,'Needs further checking'],
['F12','Shape elongation',1,50,'ratio',1,1,50,1,'Not calculated by this model']
].map(([id,label,min,max,unit,scale,lo,hi,step,help])=>({id:String(id),label:String(label),min:Number(min),max:Number(max),unit:String(unit),scale:Number(scale),domain:[Number(lo),Number(hi)],step:Number(step),help:String(help),enabled:false}));
