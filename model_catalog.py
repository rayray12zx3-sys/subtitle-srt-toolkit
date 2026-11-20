"""Public open-source CT2 model identifiers used by cloud runner."""
MODEL_REPOS = {
    'tiny': 'Systran/faster-whisper-tiny',
    'base': 'Systran/faster-whisper-base',
    'small': 'Systran/faster-whisper-small',
    'medium': 'Systran/faster-whisper-medium',
    'large-v3': 'Systran/faster-whisper-large-v3',
    'large-v3-turbo': 'deepdml/faster-whisper-large-v3-turbo-ct2',
}

def get_model_repo(name):
    if name not in MODEL_REPOS:
        raise ValueError('Unknown model choice')
    return MODEL_REPOS[name]

