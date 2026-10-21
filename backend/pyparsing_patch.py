# -*- coding: utf-8 -*-
"""
Patch de compatibilité universel pour Python 3.14 + pyparsing 3.3.x / rdflib.
Résout le bogue de pyparsing._trim_arity qui inspecte les numéros de ligne de traceback
incompatibles avec le moteur CPython 3.14 et déclenche des TypeErrors
(ex: 'Param.postParse2() missing required argument' ou '<lambda>() missing required argument: x').
"""

import inspect
import sys

try:
    import pyparsing
    import pyparsing.core

    def _safe_trim_arity(func, max_limit=3):
        """Remplace _trim_arity en analysant proprement la signature sans inspection de traceback."""
        try:
            sig = inspect.signature(func)
            params = [
                p for p in sig.parameters.values()
                if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
            ]
            num_pos = len(params)
            has_varargs = any(p.kind == p.VAR_POSITIONAL for p in sig.parameters.values())

            if has_varargs:
                return func

            if num_pos == 1:
                return lambda s, l, t: func(t)
            elif num_pos == 2:
                return lambda s, l, t: func(l, t)
            elif num_pos >= 3:
                return lambda s, l, t: func(s, l, t)
            elif num_pos == 0:
                return lambda s, l, t: func()
        except Exception:
            pass

        # Fallback adaptatif
        def _wrapper(*args):
            for i in range(len(args), -1, -1):
                try:
                    return func(*args[-i:] if i > 0 else ())
                except TypeError:
                    continue
            return func(*args)

        return _wrapper

    pyparsing.core._trim_arity = _safe_trim_arity
    pyparsing._trim_arity = _safe_trim_arity
except Exception as e:
    print(f"[Patch pyparsing] Avertissement : {e}")

try:
    from rdflib.plugins.sparql.parserutils import Param, ParamValue
    def _safe_postParse2(self, *args, **kwargs):
        toks = args[-1] if args else kwargs.get("tokenList", [])
        return ParamValue(self.name, toks, self.isList)
    Param.postParse2 = _safe_postParse2
except Exception:
    pass
