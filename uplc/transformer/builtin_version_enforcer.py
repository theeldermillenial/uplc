"""Builtin version enforcement — reject scripts using builtins from wrong version.

Haskell ref: Cardano.Ledger.Plutus.Language.deserialiseScript
validates that scripts only use builtins available in their declared
Plutus version. PlutusV1 scripts cannot use SerialiseData (V2+),
PlutusV2 scripts cannot use BLS builtins (V3+), etc.

This enforcement happens at deserialization time (flat decoding),
not at textual parsing time.
"""

from ..ast import BuiltIn, BuiltInFun, Program
from ..util import NodeVisitor


class UnsupportedBuiltin(ValueError):
    """Raised when a script uses a builtin not available in its version."""

    def __init__(self, builtin_name: str, program_version: tuple):
        self.builtin_name = builtin_name
        self.program_version = program_version
        super().__init__(
            f"Builtin '{builtin_name}' is not available in program "
            f"version {'.'.join(map(str, program_version))}"
        )


# UPLC program version doesn't distinguish PlutusV1 from PlutusV2 —
# both use (1, 0, 0). Only PlutusV3 uses (1, 1, 0). The V1/V2 builtin
# distinction is enforced at the Cardano ledger layer, not inside UPLC.
#
# At the UPLC level we can only enforce:
# - Programs (1, 0, 0): IDs 0-53 (V1 + V2 builtins)
# - Programs (1, 1, 0): all builtins including V3 (IDs 54+)
#
# Haskell ref: PlutusLedgerApi.Common.Versions
# Haskell ref: PlutusCore/Default/Builtins.hs (BuiltinSemanticsVariant)
_V3_MIN_ID = 54  # IDs 54+ require program version 1.1.0


def _builtin_version(builtin: BuiltInFun) -> tuple:
    """Return the minimum UPLC program version for a builtin."""
    if builtin.value >= _V3_MIN_ID:
        return (1, 1, 0)
    return (1, 0, 0)


class BuiltinVersionEnforcer(NodeVisitor):
    """Scan AST and reject builtins not available in the program version.

    Usage:
        enforcer = BuiltinVersionEnforcer()
        enforcer.visit(program)  # raises UnsupportedBuiltin if invalid
    """

    def __init__(self):
        self.version = (1, 0, 0)

    def visit_Program(self, node: Program):
        self.version = node.version
        self.visit(node.term)

    def visit_BuiltIn(self, node: BuiltIn):
        min_version = _builtin_version(node.builtin)
        if self.version < min_version:
            raise UnsupportedBuiltin(node.builtin.name, self.version)
        self.generic_visit(node)
