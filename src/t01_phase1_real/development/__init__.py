"""Unified development runtime extensions; scientific consumption remains disabled."""
__all__ = ['Runtime']


def __getattr__(name):
    # Native workers can import their own module without loading every backend
    # adapter and its unrelated dependencies into a model environment.
    if name == 'Runtime':
        from .runtime import Runtime
        return Runtime
    raise AttributeError(name)
