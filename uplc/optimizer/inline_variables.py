from collections import defaultdict

from ..util import NodeTransformer, NodeVisitor
from ..ast import *

"""
Inlines variable bindings (Apply(Lambda(var, body), value)) when:
  1. var appears exactly once in body (counting all occurrences)
  2. that single occurrence is in a position guaranteed to be executed
     (not inside a Lambda body or Delay term)

This is semantically correct because:
  - The variable will always be evaluated (guaranteed position)
  - Inlining doesn't duplicate evaluation (single occurrence)
  - Any side effects (crashes) will still occur (guaranteed position)

NOTE: This optimization may reorder evaluation relative to other sub-expressions
in the body (e.g. traces), so it is an O3-only optimization.
NOTE: This optimization requires unique variable names.
"""


class VariableOccurrenceCounter(NodeVisitor):
    """Counts ALL occurrences of each variable name in the AST,
    including those inside lambdas and delays."""

    def __init__(self):
        self.counts = defaultdict(int)

    def visit_Variable(self, node: Variable):
        self.counts[node.name] += 1


class GuaranteedExecutionChecker(NodeVisitor):
    """Checks if a specific variable occurs in a position that is guaranteed
    to be executed when the enclosing expression is evaluated.

    A position is guaranteed if it is NOT nested inside a Lambda body or a
    Delay term (because Lambda bodies only execute when the lambda is called,
    and Delay terms only execute when forced).

    The scrutinee of a Case is guaranteed (evaluated unconditionally), but the
    case branches are not (only one branch is taken).
    All fields of a Constr are guaranteed (all evaluated to build the value).
    """

    def __init__(self, var_name: str):
        self.var_name = var_name

    def visit_Variable(self, node: Variable) -> bool:
        return node.name == self.var_name

    # Lambda bodies are NOT guaranteed to execute
    def visit_Lambda(self, node: Lambda) -> bool:
        return False

    def visit_BoundStateLambda(self, node: BoundStateLambda) -> bool:
        return False

    # Delay terms are NOT guaranteed to execute until forced
    def visit_Delay(self, node: Delay) -> bool:
        return False

    def visit_BoundStateDelay(self, node: BoundStateDelay) -> bool:
        return False

    def visit_Apply(self, node: Apply) -> bool:
        # Both function and argument are always evaluated (call-by-value)
        return self.visit(node.f) or self.visit(node.x)

    def visit_Force(self, node: Force) -> bool:
        # The forced term is always evaluated
        return self.visit(node.term)

    def visit_Case(self, node: Case) -> bool:
        # Only the scrutinee is unconditionally evaluated; branches are not
        return self.visit(node.scrutinee)

    def visit_Constr(self, node: Constr) -> bool:
        # All constructor fields are evaluated unconditionally
        return any(self.visit(f) for f in node.fields)

    def visit_Program(self, node: Program) -> bool:
        return self.visit(node.term)

    def generic_visit(self, node: AST) -> bool:
        # For any other node (constants, builtins, errors, …) the variable
        # is not present, so return False.
        return False


class Substitute(NodeTransformer):
    """Substitutes all occurrences of var_name with value."""

    def __init__(self, var_name: str, value: AST):
        self.var_name = var_name
        self.value = value

    def visit_Variable(self, node: Variable) -> AST:
        if node.name == self.var_name:
            return self.value
        return node


class InlineVariableOptimizer(NodeTransformer):
    """Inlines variable bindings that are used exactly once in a guaranteed
    execution position.

    For Apply(Lambda(var, body), value):
      - If var appears exactly once in body
      - AND that occurrence is in a guaranteed-execution position
      then replace with body[var := value].

    Requires unique variable names (run UniqueVariableTransformer first).
    """

    def visit_Apply(self, node: Apply) -> AST:
        if isinstance(node.f, Lambda):
            var_name = node.f.var_name
            body = node.f.term
            value = node.x

            # Count all occurrences of var_name in body
            counter = VariableOccurrenceCounter()
            counter.visit(body)
            total_count = counter.counts.get(var_name, 0)

            if total_count == 1:
                # Check if the single occurrence is in a guaranteed position
                if GuaranteedExecutionChecker(var_name).visit(body):
                    # Safe to inline: substitute var with value in body
                    new_body = Substitute(var_name, value).visit(body)
                    return self.visit(new_body)

        return super().generic_visit(node)
