-- case on integer: selects branch by tag (SOP support)
(program 1.1.0
    (case (con integer 1) (lam x x) (lam x x))
)
