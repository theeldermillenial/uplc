-- case on integer: selects branch by tag value (SOP support)
-- Confirmed by Plutus conformance: term/constant-case/integer/integer-02
-- Haskell CEK machine maps integer value to constructor tag
(program 1.1.0
    (case (con integer 1) (lam x x) (lam x x))
)
