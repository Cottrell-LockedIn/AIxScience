// Feature wording is the model's own: `name` and `column` are copied verbatim from configs/features_v1.yaml
// (the frozen v1 feature registry read by `python -m qc features`). Do not paraphrase them here.
export type ModelFeature = {id:string;column:string;name:string;modelUnit:string;definition:string};
export const modelFeatures:Record<string,ModelFeature> = Object.fromEntries(([
['F01','F01_c0_area_fraction','void area fraction','fraction','class-0 pixels / analysed pixels of the stitched per-image mask'],
['F02','F02_c2_area_fraction','silicon area fraction','fraction','class-2 pixels / analysed pixels of the stitched per-image mask'],
['F03','F03_c2_eqdiam_median_px','silicon particle equivalent diameter, median','px','median over interior class-2 particles (8-connected, >= min_object_px, not touching the border) of sqrt(4 A / pi)'],
['F04','F04_c2_eqdiam_p90_px','silicon particle equivalent diameter, 90th percentile','px','90th percentile of the same particle set as F03'],
['F05','F05_c2_count_density_per_Mpx','silicon particle count density','1/Mpx','class-2 particles counted with an unbiased counting frame per 1e6 analysed px'],
['F06','F06_c2_clark_evans_R','silicon Clark-Evans nearest-neighbour ratio','ratio','mean nearest-neighbour distance between class-2 particle centroids / CSR expectation with Donnelly edge correction (R < 1 clustered, R = 1 random, R > 1 regular)'],
['F07','F07_c2_solidity_area_weighted_median','silicon particle solidity, area-weighted median','ratio','area-weighted median over interior class-2 particles of particle area / convex hull area'],
['F08','F08_c0_local_thickness_median_px','void local thickness, median','px','median over class-0 pixels of the Hildebrand-Rueegsegger local thickness (diameter of the largest inscribed disc containing the pixel)'],
['F09','F09_c0_chord_anisotropy_h_over_v','void chord-length anisotropy','ratio','mean horizontal chord length / mean vertical chord length through class 0; border-touching chords excluded as censored'],
['F10','F10_c0_fraction_iqr_512px','void fraction heterogeneity','fraction','interquartile range of the class-0 area fraction over non-overlapping 512 px windows fully inside the analysed area'],
['F11','F11_c2_perimeter_fraction_adjacent_c0','silicon perimeter fraction adjacent to void','fraction','among class-2 boundary pixels, the fraction with at least one class-0 4-neighbour'],
] as const).map(([id,column,name,modelUnit,definition])=>[id,{id,column,name,modelUnit,definition}]));
export const modelFeatureName=(id?:string)=>modelFeatures[id||'']?.name;
export const modelFeatureColumn=(id?:string)=>modelFeatures[id||'']?.column;

export type Criterion = {id:string;label:string;column:string;min:number;max:number;unit:string;enabled:boolean;scale:number;domain:[number,number];step:number;help:string};
export const defaultCriteria:Criterion[] = [
['F01',5,80,'%',100,0,100,1,'Sensitive to image segmentation'],
['F02',0,60,'%',100,0,100,1,'Sensitive to image segmentation'],
['F03',5,1200,'px',1,0,2000,1,'Sensitive to image segmentation'],
['F04',5,2000,'px',1,0,3000,1,'Sensitive to image segmentation'],
['F05',0,30000,'per Mpx',1,0,50000,100,'Sensitive to image segmentation'],
['F06',0,3,'ratio',1,0,5,0.01,'Sensitive to image segmentation'],
['F07',0,1,'ratio',1,0,1,0.01,'Sensitive to image segmentation'],
['F08',2,1200,'px',1,0,2000,1,'Needs further checking'],
['F09',0.1,10,'ratio',1,0.1,10,0.1,'Needs further checking'],
['F10',0,100,'pp',100,0,100,1,'Needs further checking'],
['F11',0,100,'%',100,0,100,1,'Needs further checking'],
['F12',1,50,'ratio',1,1,50,1,'Not calculated by this model'],
].map(([id,min,max,unit,scale,lo,hi,step,help])=>({id:String(id),label:modelFeatureName(String(id))||'void aspect ratio',column:modelFeatureColumn(String(id))||'not in features_v1 registry',min:Number(min),max:Number(max),unit:String(unit),scale:Number(scale),domain:[Number(lo),Number(hi)] as [number,number],step:Number(step),help:String(help),enabled:false}));
