import sys
sys.path.append("src")
import re
import numpy as np
from bridger import Model

# model that generates and computes the logits for the forward
# prediction of the tokens
fw_model = Model(run_name="forward", batch_size=1)
# same as forwaerts, but for the backward prediction of the tokens
# (trained on a dataset where all chars have been reverted)
bw_model = Model(run_name="backward", batch_size=1)

prefix = "Aha ! À nous les ponts !"
suffix = "Et après ces travaux ils virent que les ponts étaient bons."[::-1]

fw_tokens, _, scores, _ = fw_model.run(prefix=prefix, length=5)
# the backwards strands are generated backwards
bw_strands_rev = bw_model.gen(prefix=suffix, length=5)

# cuts the strand so that we don't end it in the middle of a word
def cleanup_strand(strand):
    return strand[: strand.rfind(" ")]


# cut at the last space
fw_strands = [cleanup_strand(fw_strand) for fw_strand in fw_model.decode(fw_tokens)]
bw_strands = [cleanup_strand(strand_rev)[::-1] for strand_rev in bw_strands_rev]

# fw_strands = ["Et à nous les tunnels, ma gente demoiselle. ", "Et ainsi, nous serons les rois de l'infrastructure... ", "Et à vous les aéroplanes, belles personnes "]
# bw_strands = [" Ils souffrirent deux ou trois lustres.", " Je les avais prévenus, mais ils n'en firent qu'à leur tête."]

# these are the locations where we may want to cut the strands for recombinations
all_fw_cut_indices = [
    [i for i, letter in enumerate(fw_strand) if letter == " "]
    for fw_strand in fw_strands
]
all_bw_cut_indices = [
    [i for i, letter in enumerate(bw_strand) if letter == " "]
    for bw_strand in bw_strands
]

# returns a (fairly long) list of possible bridges, that we will then evaluate
# through their forward likelihood
def generate_possible_bridges(fw_strands, bw_strands):
    print('inside the possibilities')
    count = 0
    possible_bridges = []
    for (fw_strand, fw_cut_indices) in zip(fw_strands, all_fw_cut_indices):
        for fw_index in fw_cut_indices:
            for (bw_strand, bw_cut_indices) in zip(bw_strands, all_bw_cut_indices):
                for bw_index in bw_cut_indices:
                    # riddance of space in fw_strand, kept in bw_strand
                    possible_bridge = fw_strand[:fw_index] + bw_strand[bw_index:]
                    br_clean = re.sub(r"(\t|\n)", " ", possible_bridge)
                    print(f"{br_clean}")
                    possible_bridges.append(possible_bridge)
                    count +=1
    print()
    print(f"count: {count}")
    return np.array(possible_bridges)


print("forward strands:")
print(fw_strands)
print('-'*40)
print("backward strands:")
print(bw_strands)
print('-'*40)

possible_bridges = generate_possible_bridges(fw_strands, bw_strands)
print('-'*40)
print()
print('now perplexiculating...')
perps = fw_model.get_perplexity(possible_bridges)
# https://stackoverflow.com/a/6979121
sorted_indz = sorted(range(len(perps)), key=perps.__getitem__)
sorted_perps = perps[sorted_indz]
sorted_bridges = possible_bridges[sorted_indz]
for sentence, perp in zip(possible_bridges, sorted_perps):
    print(f"perp: {perp:.16f} | {sentence}")
