---
license:
- mit
license_link: https://github.com/Biohub/esm/blob/main/THIRD_PARTY_NOTICE.md
language: en
tags:
- biology
- esm
- protein
- protein-structure-prediction
- structure-prediction
- protein-design
- 3d-structure
- confidence-estimation
- molecular-dynamics
- transformers
---

# ESMFold2

## Model Details

ESMFold2 is a state-of-the-art model for protein structure prediction and design that defines a new frontier for speed and accuracy. The model predicts high-resolution, all-atom 3D protein structures directly from amino acid sequences, with optional multiple sequence alignment (MSA) input for enhanced accuracy on challenging targets. The model outputs comprehensive structural information including all-atom coordinates (backbone and side chains), confidence metrics (pLDDT, pAE, pTM, iPTM), and optional distogram predictions for detailed analysis of predicted structures. Unlike ESMFold, ESMFold2 is able to predict structures for all biomolecules, including small molecules, DNA, RNA, and modified amino acids.

ESMFold2 is capable of either single-sequence or MSA conditioned structure prediction for improved accuracy on difficult targets. The ESMFold2-Fast variant is an inference optimized single-sequence structure prediction model and is not MSA conditioned.

To run this model with the Biohub Platform API, visit the [Biohub Platform](https://biohub.ai/).

Read more about ESMFold2 in our paper [here](https://www.biorxiv.org/content/10.64898/2026.06.03.729735).

## Model Variants

| Model | MSA Conditioning | Description | Data Cutoff |
| :---- | :---- | :---- | :---- |
| [ESMFold2](https://huggingface.co/biohub/ESMFold2) | Yes | Large model, capable of either single-sequence or MSA conditioned structure prediction for improved accuracy on difficult targets | Sept 2021 |
| [ESMFold2-Fast](https://huggingface.co/biohub/ESMFold2-Fast) | No | Inference optimized single-sequence structure prediction model | Sept 2021 |

## Performance Metrics

ESMfold2 was evaluated against state-of-the-art single-sequence and MSA-based structure prediction models on the FoldBench benchmark. ESMFold2 meets or exceeds performance by AlphaFold3 on antibody-antigen complex prediction, protein-protein complex prediction and [Runs N' Poses](https://www.biorxiv.org/content/10.1101/2025.02.03.636309v1) benchmarks. Inference-time compute can dramatically improve performance of ESMFold2, especially across antibody-antigen complexes.

![][image1]

Refer to the [paper](https://www.biorxiv.org/content/10.64898/2026.06.03.729735) for details on additional performance metrics.

### Usage

Please install `esm` from GitHub (a PyPI release is coming soon):

```
pip install esm@git+https://github.com/Biohub/esm.git@main
```

You can fold your first protein with:

```py
from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model

# Ubiquitin (PDB 1UBQ)
sequence = "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"

# optionally use "biohub/ESMFold2"
model = ESMFold2Model.from_pretrained("biohub/ESMFold2-Fast").cuda().eval()
output = model.infer_protein(sequence, num_loops=3, num_sampling_steps=50)

print(f"pLDDT mean: {float(output['plddt'].mean()):.3f}, pTM: {float(output['ptm'].mean()):.3f}")
```

You can also fold complex biomolecules — proteins, DNA/RNA (with modified residues), and small-molecule ligands all at once. Here's an example folding the HhaI DNA methyltransferase + its cognate DNA (with a trapped 5-fluoro-2′-deoxycytidine, CCD `C36`) + the SAH cofactor (PDB [1MHT](https://www.rcsb.org/structure/1MHT)):

```py
from esm.models.esmfold2 import (
    DNAInput,
    ESMFold2InputBuilder,
    LigandInput,
    Modification,
    ProteinInput,
    StructurePredictionInput,
)
from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model

HHAI_SEQ = (
    "MIEIKDKQLTGLRFIDLFAGLGGFRLALESCGAECVYSNEWDKYAQEVYEMNFGEKPEGDITQVNEKTIPDH"
    "DILCAGFPCQAFSISGKQKGFEDSRGTLFFDIARIVREKKPKVVFMENVKNFASHDNGNTLEVVKNTMNELD"
    "YSFHAKVLNALDYGIPQKRERIYMICFRNDLNIQNFQFPKPFELNTFVKDLLLPDSEVEHLVIDRKDLVMTN"
    "QEIEQTTPKTVRLGIVGKGGQGERIYSTRGIAITLSAYGGGIFAKTGGYLVNGKTRKLHPRECARVMGYPDS"
    "YKVHPSTSQAYKQFGNSVVINVLQYIAYNIGSSLNFKPY"
)

model = ESMFold2Model.from_pretrained("biohub/ESMFold2").cuda().eval()

spi = StructurePredictionInput(
    sequences=[
        ProteinInput(id="A", sequence=HHAI_SEQ),
        DNAInput(
            id="B",
            sequence="GATAGCGCTATC",
            modifications=[Modification(position=5, ccd="C36")],
        ),
        DNAInput(
            id="C",
            sequence="TGATAGCGCTATC",
            modifications=[Modification(position=6, ccd="C36")],
        ),
        LigandInput(id="L", ccd=["SAH"]),
    ]
)

result = ESMFold2InputBuilder().fold(
    model, spi, num_loops=3, num_sampling_steps=50, num_diffusion_samples=1, seed=0
)

print(f"pLDDT mean: {float(result.plddt.mean()):.3f}, pTM: {float(result.ptm):.3f}, ipTM: {float(result.iptm):.3f}")

with open("1mht_pred.cif", "w") as f:
    f.write(result.complex.to_mmcif())
```

For the Biohub API, first generate an [API key](https://biohub.ai/developer-console/api-keys) and add it to your Biohub account. The code below assumes the environment variable `ESM_API_KEY=$YOUR_API_KEY`.

```py
import os

from esm.models.esmfold2 import (
    DNAInput,
    LigandInput,
    Modification,
    ProteinInput,
    StructurePredictionInput,
)
from esm.sdk import esmfold2_client
from esm.sdk.api import FoldingConfig

HHAI_SEQ = (
    "MIEIKDKQLTGLRFIDLFAGLGGFRLALESCGAECVYSNEWDKYAQEVYEMNFGEKPEGDITQVNEKTIPDH"
    "DILCAGFPCQAFSISGKQKGFEDSRGTLFFDIARIVREKKPKVVFMENVKNFASHDNGNTLEVVKNTMNELD"
    "YSFHAKVLNALDYGIPQKRERIYMICFRNDLNIQNFQFPKPFELNTFVKDLLLPDSEVEHLVIDRKDLVMTN"
    "QEIEQTTPKTVRLGIVGKGGQGERIYSTRGIAITLSAYGGGIFAKTGGYLVNGKTRKLHPRECARVMGYPDS"
    "YKVHPSTSQAYKQFGNSVVINVLQYIAYNIGSSLNFKPY"
)

client = esmfold2_client(model="esmfold2-fast-2026-05", token=os.environ["ESM_API_KEY"])

spi = StructurePredictionInput(
    sequences=[
        ProteinInput(id="A", sequence=HHAI_SEQ),
        DNAInput(
            id="B",
            sequence="GATAGCGCTATC",
            modifications=[Modification(position=5, ccd="C36")],
        ),
        DNAInput(
            id="C",
            sequence="TGATAGCGCTATC",
            modifications=[Modification(position=6, ccd="C36")],
        ),
        LigandInput(id="L", ccd=["SAH"]),
    ]
)

result = client.fold_all_atom(spi, config=FoldingConfig(num_loops=3, num_sampling_steps=50))

print(f"pLDDT mean: {float(result.plddt.mean()):.3f}, pTM: {float(result.ptm):.3f}, ipTM: {float(result.iptm):.3f}")
```

For multi-chain complexes (e.g. antibody–antigen), you can supply paired MSAs to take advantage of inter-chain co-evolution. See the [ESMFold2 tutorial](https://github.com/biohub/esm/blob/main/cookbook/tutorials/esmfold2.ipynb) for details.

## Training Data

ESMfold2 was trained on sequences from the Protein Data Bank (PDB) and the AlphaFold DB (AFDB).

## Frontier Safety

Biohub has established a safety team to assess the benefits and potential risks of our models and tools prior to release, and develop mitigations where necessary. Risk assessment was conducted for ESMFold2 prior to release. Further details are available in our corresponding paper appendix.

Informed by our risk assessments, we are releasing the source code and model weights for ESMFold2.

[Biohub.ai](http://Biohub.ai) Platform: We implement guardrails that detect and restrict the use of keywords and sequences corresponding to controlled pathogens and toxins on our freely accessible platform. For further details regarding these guardrails, please refer to our Biohub platform Resources page.

## Biases and Limitations

- **Dataset biases**: The model may reflect biases present in the training data (PDB, AFDB), including over-representation of certain protein families, experimental conditions, or structural classes. Performance may vary for underrepresented protein types.
- **Dataset limitations:** PDB historically lacks comprehensive data on protein conformations, post-translational modifications, disordered regions, etc. Like all other structure prediction models trained on the PDB, performance may degrade on other biomolecules.
- **Computational demand:** Highest accuracy structure predictions require scaling inference time compute. Predictions made with reduced inference parameters may lead to suboptimal performance.
- **Experimental validation required**: All predictions should be considered hypotheses requiring experimental validation. The model cannot replace experimental structure determination methods (X-ray crystallography, cryo-EM, NMR) for definitive structural characterization.

### Out-of-Scope or Unauthorized Use Cases

Do not use the model for the following purposes:

- Any use that is prohibited by the [Acceptable Use Policy](https://biohub.org/acceptable-use-policy/).

### Caveats and Recommendations

- Always review and validate outputs generated by the model.
- Treat model outputs as machine-generated hypotheses that require further experimental validation, not as established biological facts.
- We are committed to advancing the responsible development and use of artificial intelligence.

Should you have any security or privacy issues or questions related to this model, please reach out to our team at [support@biohub.org](mailto:support@biohub.org).

### Citation

```
@misc{candido2026language,
  title  = {Language Modeling Materializes a World Model of Protein Biology},
  author = {Candido, Salvatore and Hayes, Thomas and Derry, Alexander and Rao, Roshan
            and Lin, Zeming and Verkuil, Robert and Wu, Bryan and Lee, Jin Sub
            and Bruguera, Elise S. and Keval, Jehan A. and Kopylov, Mykhailo
            and Pak, John E. and Wu, Wesley and Thomas, Neil and Mataraso, Samson
            and Hsu, Alvin and Trotman-Grant, Ashton C. and Fatras, Kilian
            and dos Santos Costa, Allan and Badkundri, Rohil and Ak{\i}n, Halil
            and Oktay, Deniz and Deaton, Jonathan and Montabana, Elizabeth
            and Sitwala, Hrishita and Yu, Yue and Wiggert, Marius
            and Carlin, Dylan Alexander and Goering, Anthony W. and Blazejewski, Tomasz
            and Sandora, McCullen and Hla, Michael and Jia, Tina Z.
            and Kloker, Leon H. and Sofroniew, Nicholas J. and Uehara, Masatoshi
            and Pannu, Jassi and Bachas, Sharrol and Liu, Daniel S.
            and Sercu, Tom and Rives, Alexander},
  year   = {2026},
  url    = {https://www.biorxiv.org/content/10.64898/2026.06.03.729735},
  note   = {Preprint}
}
```

## Acknowledgements

Many people on the Biohub AI Research team and prior EvolutionaryScale team contributed to the development of this model. It would not have been possible without them.

[image1]: images/folding_evals.png
