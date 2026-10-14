"""Exact token reconstruction from the original-package observer; no inference replacement."""
import hashlib
from .raw_format import require

def validate_trace(events, sequence):
    tokenized = [e for e in events if e['event']=='tokenized']
    chunks = [e for e in events if e['event']=='chunk_completed']
    embeddings = [e for e in events if e['event']=='embedding_completed']
    require(len(tokenized)==len(embeddings)==1 and chunks, 'MISSING_TOKEN_OR_EMBEDDING_OBSERVATION')
    token = tokenized[0]
    require(token['sequence']==token['input_string']==sequence and token['sequence_sha256']==hashlib.sha256(sequence.encode()).hexdigest(), 'TOKEN_INPUT_MISMATCH')
    require(token['token_count']==len(token['token_ids'])==len(token['decoded_tokens']), 'TOKEN_COUNT_MISMATCH')
    left, right = int(token['prepend_bos']), len(token['decoded_tokens'])-int(token['append_eos'])
    require(''.join(token['decoded_tokens'][left:right])==sequence, 'TOKEN_RECONSTRUCTION_MISMATCH')
    require(token['decoded_tokens'][0]=='<cls>' and token['decoded_tokens'][-1]=='<eos>'
            and token['prepend_bos'] and token['append_eos'], 'UNEXPECTED_PINNED_ALPHABET_SPECIAL_TOKENS')
    reconstructed = []
    cursor = 0
    for chunk in chunks:
        require(chunk['start']==cursor, 'CHUNK_POSITION_GAP_OR_OVERLAP')
        ids = chunk['token_ids']
        require(ids and ids==token['token_ids'][cursor:chunk['requested_end']], 'CHUNK_TOKEN_MISMATCH')
        require(chunk['representation_shape']==[1,len(ids),1280] and chunk['finite'], 'INVALID_CHUNK_REPRESENTATION')
        reconstructed.extend(ids)
        cursor += len(ids)
    require(reconstructed==token['token_ids'], 'INCOMPLETE_TOKEN_COVERAGE')
    require(embeddings[0]['shape']==[len(sequence),1280] and embeddings[0]['finite'], 'INVALID_EMBEDDING_SHAPE_OR_VALUES')
    return dict(amino_acids=len(sequence), token_count=token['token_count'],
        chunk_token_counts=[len(c['token_ids']) for c in chunks],
        chunk_ranges_0based_half_open=[[c['start'],c['start']+len(c['token_ids'])] for c in chunks],
        exact_token_reconstruction=True, embedding_shape=embeddings[0]['shape'])

