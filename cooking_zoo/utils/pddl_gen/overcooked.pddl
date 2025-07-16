(define (domain overcooked)
    (:requirements :typing :derived-predicates :negative-preconditions :conditional-effects :adl) ; allows conjunction, disjunction, quantifiers, etc.

    ;;--------------------------------------------------------------------
    ;; Types (reflect class hierarchy in world_objects.py)
    ;;--------------------------------------------------------------------
    (:types
        food-tag location static-object dynamic-object direction ingredient-type integer - object
        counter deliversquare appliance - static-object
        agent pickable-object - dynamic-object
        plate ingredient - pickable-object
        onion tomato lettuce cucumber apple watermelon bread smash-ingredient - ingredient
        carrot banana - smash-ingredient
        cutboard blender - appliance

    ) ; 

   
    (:constants ;; need to be in front of the predicates
        agent-01 - agent
        dir-down dir-left dir-right dir-up - direction

        tomato-salad-food tomato-lettuce-salad-food tomato-lettuce-onion-salad-food carrot-banana-food mashed-carrot-banana-food cucumber-onion-food apple-watermelon-food - food-tag ; food names

        ;; ingredient type 
        onion-type tomato-type lettuce-type cucumber-type apple-type watermelon-type bread-type carrot-type banana-type - ingredient-type ; ingredient types

        ;; number 
        num0 num1 num2 - integer
    )

    ;;--------------------------------------------------------------------
    ;; Predicates
    ;;--------------------------------------------------------------------
    (:predicates
        ;; number succ
        (succ ?n1 - integer ?n2 - integer) ; successor relation for numbers
        (chopped-food-count ?c - cutboard ?num - integer)
        (smashed-food-count ?c - blender ?num - integer)
        (quantity-after-chop ?ing-type - ingredient-type ?num - integer)
        (clear ?l - location) ; whether location is empty
        (on ?s - static-object ?l - location) ; static object is at location
        (at ?d - dynamic-object ?l - location) ; dynamic object is at location (movable)
        (move-dir ?lf - location ?lt - location ?dir - direction) ; adjacent location and how to get there
        (holding ?ag - agent ?x - pickable-object) ; agent holds item
        (handempty ?ag - agent)
        (on-plate ?i - ingredient ?p - plate) ; ingredient is on plate
        (isfood ?p - plate ?f - food-tag) ; plate can be viewed as a food of a certain type
        (served ?p - plate ?f - food-tag) ; plate and its food has been served
        (get-chopped ?i - ingredient) ; whether ingredient is chopped
        (get-smashed ?i - smash-ingredient) ; whether ingredient is smashed
        (cutboard-contain ?c - cutboard ?i - ingredient) ; cutboard contains ingredient
        (blender-contain ?b - blender ?i - smash-ingredient) ; blender contains ingredient
        (has-type ?i - ingredient ?t - ingredient-type) ; similar to the typing but this is used for functions
        (is-block ?l - location) ; whether the location is a block
        (is-switch ?l - location) ; whether location is a switch
        (switch-on ?l - location) ; whether switch is on
        (block-on ?l - location) ; whether a block is on the location
    ) ; 

    ;;--------------------------------------------------------------------
    ;; Primitive actions
    ;;--------------------------------------------------------------------

    ;; ------------------------------------------------ Move one step
    (:action move
        :parameters (?ag - agent ?from ?to - location ?dir - direction)
        :precondition (and
            (at ?ag ?from)
            (move-dir ?from ?to ?dir)
            (clear ?to) ; destination must be empty
            (not (is-switch ?to)) ; destination must not be a switch
            (imply
                (is-block ?to)
                (not (block-on ?to))) ; if the destination is a block, it must not be on the block
        )
        :effect (and
            (at ?ag ?to) ; agent is now at destination
            (not (at ?ag ?from)) ; agent is no longer at source
            (not (clear ?to)) ; source is no longer empty
            (clear ?from) ; destination is now empty
        )
    )

    (:action move-to-switch-on
        :parameters (?ag - agent ?from ?to - location ?dir - direction)
        :precondition (and
            (at ?ag ?from)
            (is-switch ?to)
            (move-dir ?from ?to ?dir) ; assume switch is always reachable
            (clear ?to) ; destination must be empty
            (not (switch-on ?to)) ; switch must be off
        )
        :effect (and
            (at ?ag ?to)
            (not (at ?ag ?from))
            (not (clear ?to))
            (clear ?from)
            (switch-on ?to) ; switch is now on
            ;; modify the blocks 
            (forall
                (?b - location)
                (when
                    (and (is-block ?b) (not (block-on ?b)))
                    (and (block-on ?b)
                        (not (clear ?b)) ; block is now on the location
                    )
                )
            )
        )
    )
    (:action move-to-switch-off
        :parameters (?ag - agent ?from ?to - location ?dir - direction)
        :precondition (and
            (at ?ag ?from)
            (is-switch ?to)
            (move-dir ?from ?to ?dir) ; assume switch is always reachable
            (clear ?to) ; destination must be empty
            (switch-on ?to) ; switch must be on
        )
        :effect (and
            (at ?ag ?to)
            (not (at ?ag ?from))
            (not (clear ?to))
            (clear ?from)
            (not (switch-on ?to)) ; switch is now off
            ;; modify the blocks 
            (forall
                (?b - location)
                (when
                    (and (is-block ?b) (block-on ?b))
                    (and (not (block-on ?b))
                        (clear ?b) ; block is now off the location
                    )
                )
            )
        )
    )

    ;; ------------------------------------------------ Pick an item lying at the same tile
    (:action pick-up
        :parameters (?ag - agent ?it - pickable-object ?agloc ?itemloc - location ?dir - direction)
        :precondition (and
            (at ?ag ?agloc)
            (at ?it ?itemloc)
            (handempty ?ag)
            (move-dir ?agloc ?itemloc ?dir) ; agent can reach the item
            (
            forall(?s - appliance)
                (not (on ?s ?itemloc))
            )
        )
        :effect (and
            (holding ?ag ?it) ; agent is now holding the item
            (not (at ?it ?itemloc)) ; item is no longer at the location
            (not (handempty ?ag)) ; agent is no longer handempty
        )
    )


        ;; ------------------------------------------------ Put the held item down on the current tile
    (:action put-down
        :parameters (?ag - agent ?it - pickable-object ?agloc ?targetloc - location ?dir - direction)
        :precondition (and
            (at ?ag ?agloc)
            (holding ?ag ?it)
            (move-dir ?agloc ?targetloc ?dir) ; agent can reach the item
            (or 
                (exists (?s - static-object)
                 (and (on ?s ?targetloc)
                 ))
            )
        )
        :effect (and 
            (at ?it ?targetloc) ; item is now at the target location
            (not (holding ?ag ?it)) ; agent is no longer holding the item
            (handempty ?ag) ; agent is now handempty
        )
    )

    ;; ------------------------------------------------ (Appliance Use)
    (:action chop
        :parameters (?ag - agent ?ing - ingredient ?agloc ?targetloc - location ?cb - cutboard ?ing-type - ingredient-type ?z - integer ?dir - direction)
        :precondition (and
            (at ?ag ?agloc)
            (move-dir ?agloc ?targetloc ?dir) ; agent can reach the target location 
            ; target location must a chopboard
            (on ?cb ?targetloc)
            (chopped-food-count ?cb num0) ; cutboard is empty
            ; the ingredient is already at the target location
            (at ?ing ?targetloc)
            (has-type ?ing ?ing-type)
            (quantity-after-chop ?ing-type ?z)
            
        )
        :effect (and
            (not (at ?ing ?targetloc)) ; ingredient is no longer at the target location
            (cutboard-contain ?cb ?ing) ; cutboard now contains the ingredient
            (get-chopped ?ing) ; ingredient is now chopped
            (chopped-food-count ?cb ?z) ; cutboard now has chopped food to the quantity of z
            (not (chopped-food-count ?cb num0)) ; cutboard is no longer empty
        )
    )
    (:action smash
        :parameters (?ag - agent ?ing - smash-ingredient ?agloc ?targetloc - location ?bl - blender ?dir - direction)
        :precondition (and
            (at ?ag ?agloc)
            (move-dir ?agloc ?targetloc ?dir) ; agent can reach the target location 
            ; target location must a blender
            (on ?bl ?targetloc)
            (smashed-food-count ?bl num0) ; blender is empty
            ; the ingredient is already at the target location
            (at ?ing ?targetloc)
        )
        :effect (and 
            (not (at ?ing ?targetloc)) ; ingredient is no longer at the target location
            (blender-contain ?bl ?ing) ; blender now contains the ingredient
            (get-smashed ?ing) ; ingredient is now smashed
            (smashed-food-count ?bl num1) ; blender now has smashed food to the quantity of 1
            (not (smashed-food-count ?bl num0)) ; blender is no longer empty
        )
    )

    (:action collect-chopped
        :parameters (?ag - agent ?cb - cutboard ?ing - ingredient ?agloc ?targetloc - location ?z - integer ?precz - integer ?dir - direction)
        :precondition (and 
            (at ?ag ?agloc)
            (handempty ?ag)
            (move-dir ?agloc ?targetloc ?dir) ; agent can reach the target location 
            ; target location must a chopboard
            (on ?cb ?targetloc)
            (not (chopped-food-count ?cb num0)) ; cutboard has chopped food
            (chopped-food-count ?cb ?z) ; cutboard has chopped food to the quantity of z
            (succ ?precz ?z)
            (cutboard-contain ?cb ?ing) ; cutboard contains the ingredient
        )
        :effect (and 
            (not (chopped-food-count ?cb ?z)) ; cutboard no longer has chopped food to the quantity of z
            (chopped-food-count ?cb ?precz) ; cutboard now has chopped food to the quantity of precz
            (holding ?ag ?ing) ; agent is now holding the ingredient
            (when 
            (chopped-food-count ?cb num0) ; if there is no chopped food left
                (not (cutboard-contain ?cb ?ing)) ; cutboard no longer contains the ingredient
            )
        )
    )

    (:action collect-smashed
        :parameters (?ag - agent ?bl - blender ?ing - smash-ingredient ?agloc ?targetloc - location ?z ?precz - integer ?dir - direction)
        :precondition (and
            (at ?ag ?agloc)
            (handempty ?ag)
            (move-dir ?agloc ?targetloc ?dir) ; agent can reach the target location 
            ; target location must a blender
            (on ?bl ?targetloc)
            (not (smashed-food-count ?bl num0)) ; blender has smashed food
            (smashed-food-count ?bl ?z) ; blender has smashed food to the quantity of z
            (succ ?precz ?z) ;; successor relation for numbers
            (blender-contain ?bl ?ing) ; blender contains the ingredient    
        )
        :effect (and
            (not (smashed-food-count ?bl ?z)) ; blender no longer has smashed food to the quantity of z
            (smashed-food-count ?bl ?precz) ; blender now has smashed food to the quantity of precz
            (holding ?ag ?ing) ; agent is now holding the ingredient
            (when
                (and (smashed-food-count ?bl num0))
                (not (blender-contain ?bl ?ing)) ; blender no longer contains the ingredient
            ) ; if there is no smashed food left and blender still contains the ingredient
        )
    )

    (:action put-on-plate
        :parameters (?ag - agent ?it - ingredient ?agloc ?targetloc - location ?pl - plate ?dir - direction)
        :precondition (and
            (at ?ag ?agloc)
            (holding ?ag ?it) ; agent is holding the ingredient
            (move-dir ?agloc ?targetloc ?dir) ; agent can reach the target location 
            (at ?pl ?targetloc) ; target location must be a plate
        )
        :effect (and
            (not (holding ?ag ?it)) ; agent is no longer holding the ingredient
            (handempty ?ag) ; agent is now handempty
            (on-plate ?it ?pl) ; ingredient is now on the plate
        )
    )

    ;; serve the food 
    (:action serve-food
        :parameters (?ag - agent ?pl - plate ?f - food-tag ?agloc ?targetloc - location ?dir - direction)
        :precondition (and 
            (at ?ag ?agloc)
            (move-dir ?agloc ?targetloc ?dir) ; agent can reach the target location 
            (holding ?ag ?pl) ; agent is holding the plate
            (isfood ?pl ?f) ; plate is a food of a certain type
            (exists (?ds - deliversquare)
                (and
                    (on ?ds ?targetloc) ; target location must be a deliver square
                )
            )
        )
        :effect (and 
            (not (holding ?ag ?pl)) ; agent is no longer holding the plate
            (handempty ?ag) ; agent is now handempty
            (served ?pl ?f) ; plate and its food has been served
            (forall (?i - ingredient)
                (when (on-plate ?i ?pl)
                    (not (on-plate ?i ?pl)) ; all ingredients on the plate are no longer on the plate
                )
            )
        )
    )

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

    
    

)

