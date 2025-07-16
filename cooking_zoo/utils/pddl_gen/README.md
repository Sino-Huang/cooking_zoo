## Notes for Fast Downwards Solver Compatibility

1. 'either' keyword can only appear in the predicate definition, not in the action parameters. 
2. 'fluents' and numerical calculations are not supported by Fast Downwards.
3. The effects of actions can contain `forall` quantifiers. 
4. `imply` keyword is supported in the preconditions of actions.
5. `exists` quantifier is supported in the derived predicates.
6. `= ?x ?y/obj` is supported in the precondition / when / derived predicates.
7. in precondition or when condition, we can directly apply constants like `on plate-01 pos-1-1` instead of `on ?p - plate ?l - location`.
8. The `derived` definition can be tricky as it cannot contain "object" in the parameter, however, you can do the following so as to constrain the variable to be a specific constant/obj: 
```lisp
(:derived (isfood ?pl - plate ?f - food-tag)
        (or
            ;; tomato salad
            (and 
                (exists (?ing - tomato)
                    (and
                        (on-plate ?ing ?pl)
                        (get-chopped ?ing)
                    )
                )
                (= ?f tomato-salad-food)
            )
            ;; tomato lettuce salad
            (and
                (exists (?ing1 - tomato ?ing2 - lettuce)
                    (and
                        (on-plate ?ing1 ?pl)
                        (on-plate ?ing2 ?pl)
                        (get-chopped ?ing1)
                        (get-chopped ?ing2)
                    )
                )
                (= ?f tomato-lettuce-salad-food)
            )
        )
    )
```