# Stats: kpi_per_image
config_hash: de199d6c8d69
git_sha: bf71ff6
reference_batch: Batch_3; source: Polaron clarification; config auto resolved
phase_identity: stated by Polaron, not image-verified
images: 31; features used: 8; zero-MAD columns dropped: none
robust z: median and 1.4826*MAD per feature across all images, without batch labels
Gaussian MMD bandwidth: 4.697 (median pairwise Euclidean distance over all robust-z images)
permutations: 1000 image-label draws per pair; seed=0; plus-one p; BH over 9 pair/metric tests
Batch_3 null: 1000 random 7/10 splits, size-matched to 7-image batches; smaller reference side gives wider/conservative bands than 7/17
null p95/p99: median_shift=0.9102/1.031; energy_distance=1.729/2.208; mmd2_unbiased=0.08634/0.1422
Batch_1 vs Batch_3: median_shift=0.9307, p=0.07393; energy_distance=1.895, p=0.04695; mmd2_unbiased=0.07851, p=0.05594
Batch_2 vs Batch_3: median_shift=0.478, p=0.6344; energy_distance=1.72, p=0.1329; mmd2_unbiased=-0.03063, p=0.7702
zero Batch_3-MAD columns excluded from median shift: none
consistency rank ascending (mean pairwise Euclidean): Batch_3=4.166 (rank 1, SE 0.5095, separable=true); Batch_1=7.1 (rank 2, SE 1.327, separable=false); Batch_2=10.42 (rank 3, SE 5.388, separable=false)
