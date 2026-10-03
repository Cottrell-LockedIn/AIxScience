# Stats: dinov2_vits14_inlens_by_image
config_hash: de199d6c8d69
git_sha: bf71ff6
reference_batch: Batch_3; source: Polaron clarification; config auto resolved
phase_identity: stated by Polaron, not image-verified
images: 31; features used: 384; zero-MAD columns dropped: none
robust z: median and 1.4826*MAD per feature across all images, without batch labels
Gaussian MMD bandwidth: 28.59 (median pairwise Euclidean distance over all robust-z images)
permutations: 1000 image-label draws per pair; seed=0; plus-one p; BH over 9 pair/metric tests
Batch_3 null: 1000 random 7/10 splits, size-matched to 7-image batches; smaller reference side gives wider/conservative bands than 7/17
null p95/p99: median_shift=0.8678/0.9587; energy_distance=9.877/12.12; mmd2_unbiased=0.07578/0.1265
Batch_1 vs Batch_3: median_shift=1.303, p=0.000999; energy_distance=13.47, p=0.001998; mmd2_unbiased=0.1544, p=0.002997
Batch_2 vs Batch_3: median_shift=1.056, p=0.004995; energy_distance=11.18, p=0.00999; mmd2_unbiased=0.1278, p=0.00999
zero Batch_3-MAD columns excluded from median shift: none
consistency rank ascending (mean pairwise Euclidean): Batch_2=23.57 (rank 1, SE 1.315, separable=false); Batch_3=26.03 (rank 2, SE 0.9867, separable=false); Batch_1=30.91 (rank 3, SE 2.556, separable=false)
