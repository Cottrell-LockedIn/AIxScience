# Stats: dinov2_vits14_setype_by_image
config_hash: de199d6c8d69
git_sha: bf71ff6
reference_batch: Batch_3; source: Polaron clarification; config auto resolved
phase_identity: stated by Polaron, not image-verified
images: 31; features used: 384; zero-MAD columns dropped: none
robust z: median and 1.4826*MAD per feature across all images, without batch labels
Gaussian MMD bandwidth: 29.21 (median pairwise Euclidean distance over all robust-z images)
permutations: 1000 image-label draws per pair; seed=0; plus-one p; BH over 9 pair/metric tests
Batch_3 null: 1000 random 7/10 splits, size-matched to 7-image batches; smaller reference side gives wider/conservative bands than 7/17
null p95/p99: median_shift=0.7356/0.7876; energy_distance=8.767/9.92; mmd2_unbiased=0.04912/0.07374
Batch_1 vs Batch_3: median_shift=1.128, p=0.000999; energy_distance=12.28, p=0.000999; mmd2_unbiased=0.114, p=0.001998
Batch_2 vs Batch_3: median_shift=0.8487, p=0.004995; energy_distance=8.416, p=0.01499; mmd2_unbiased=0.05837, p=0.01998
zero Batch_3-MAD columns excluded from median shift: none
consistency rank ascending (mean pairwise Euclidean): Batch_3=26.75 (rank 1, SE 1.305, separable=false); Batch_2=27.68 (rank 2, SE 3.526, separable=false); Batch_1=35.81 (rank 3, SE 4.119, separable=false)
