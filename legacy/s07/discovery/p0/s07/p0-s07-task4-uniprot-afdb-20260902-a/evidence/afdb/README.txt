ALPHAFOLD DATABASE FTP README

This document describes the types of files available from the AlphaFold DB FTP
area at http://ftp.ebi.ac.uk/pub/databases/alphafold/.

1.) download_metadata.json
This file contains a list of all the archive files available for bulk download.
The file is in JSON format and contains a list of objects with the following
fields:

* archive_name: The name of the archive file,
  e.g. "UP000006548_3702_ARATH_v2.tar", string, required
* num_predicted_structures: The count of predicted structures in the archive,
  e.g. 27434, number, required
* size_bytes: The size of the archive file in bytes,
  e.g. 3855707136, number, required
* type: The type/category of the archive file, e.g. "proteome", string, required
* species: The scientific name of the corresponding species,
  e.g. "Homo sapiens", string, optional
* common_name: A common name of the corresponding species,
  e.g. "Human", string, optional
* latin_common_name: Indicates if the common name is in Latin,
  e.g. true, boolean, optional
* reference_proteome: The identifier of the reference proteome,
  e.g. "UP000006548", string, optional
* label: A label for the archive file,
  e.g. "Swiss-Prot (CIF files)", string, optional

2.) accession_ids.csv
This file contains a list of all the UniProt accessions that have predictions in
the current database version of AlphaFold DB. The file is in CSV format and
includes the following columns, separated by a comma:

* UniProt accession, e.g. A8H2R3
* First residue index (UniProt numbering), e.g. 1
* Last residue index (UniProt numbering), e.g. 199
* AlphaFold DB identifier, e.g. AF-A8H2R3-F1
* Latest version, e.g. 2

3.) msa_depths.csv
This file contains Multiple Sequence Alignment (MSA) depths for every entry in
the database. These depths correspond to the MSA files that have been given as
an input to AlphaFold to generate the structure prediction. The file is in CSV
format and includes the following columns, separated by a comma:

* AFDB accession, e.g. AF-A8H2R3-F1
* Multiple Sequence Alignment (MSA) depth, e.g. 1989. This is the number of
  sequences in the MSA file.

4.) sequences.fasta
This file contains sequences for all proteins in the current database version in
FASTA format.

The format for the identifier row is:
>AFDB:UniqueIdentifier ProteinName UA=UniprotAccession UI=UniprotIdentifier
 OS=OrganismName OX=OrganismIdentifier [GN=GeneName]
For example:
>AFDB:AF-Q5VSL9-F1 Striatin-interacting protein 1 UA=Q5VSL9 UI=Q5VSL9
 OS=Homo Sapiens OX=9606 GN=STRIP1

The fields in the identifier row match UniProt fields described in
https://www.uniprot.org/help/fasta-headers. The GN=GeneName field is optional
and provided only if known.

The sequence row contains the corresponding amino acid sequence. Each sequence
is on a single line, i.e. there is no wrapping.

5.) *.tar
These files are organised into several folders. The folder “latest” contains the
latest version of the archive files, while v* folders (e.g. v1, v2, etc.) have
the corresponding versions of the archive files.

The archive files are TAR archives of GZIP compressed files for atomic
coordinate data in PDB and mmCIF formats.

6.) diffs.ndjson.gz
This file lists entries that were added, removed, or changed in the current
database version. The file is newline-delimited JSON (NDJSON) compressed with 
gzip. Each line is a single record with the following fields:

id: AlphaFold DB identifier, e.g. "AF-Q5VSL9-F1", string, required

status: Change type, one of "ADDED", "REMOVED", "CHANGED", string, required

ref_len: Sequence length in the previous release, number, optional (only 
for "CHANGED")

cmp_len: Sequence length in the current release, number, optional (only 
for "CHANGED")

Example (one record per line):
{"id":"AF-A0A016SDI7-F1","status":"ADDED"}
{"id":"AF-A0A009DWB1-F1","status":"REMOVED"}
{"id":"AF-A0A017SPL2-F1","status":"CHANGED","ref_len":408,"cmp_len":409}

Note: This file is the canonical per-release diff. It can be streamed and 
filtered with standard tools (e.g. zcat, jq).