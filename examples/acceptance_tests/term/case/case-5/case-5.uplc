-- case of non-constr integer: selects branch by tag
(program 1.1.0
    (case (con integer 1) (lam x x) (lam x x))
)
