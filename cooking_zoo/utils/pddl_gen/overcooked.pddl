(define (domain overcooked)
    (:requirements :typing :derived-predicates :negative-preconditions :conditional-effects :adl) ; allows conjunction, disjunction, quantifiers, etc.

    ;;--------------------------------------------------------------------
    ;; Types (reflect class hierarchy in world_objects.py)
    ;;--------------------------------------------------------------------
    (:types
        plate ingredient food-tag location static-object dynamic-object direction - object
        counter deliversquare appliance - static-object
        agent - dynamic-object
        chop-ingredient smash-ingredient chop-smash-ingredient - ingredient
        onion tomato lettuce cucumber apple watermelon bread - chop-ingredient
        carrot banana - chop-smash-ingredient
        cutboard blender - appliance

    ) ; 
    (:constants
        agent-01 - agent
        dir-down dir-left dir-right dir-up - direction

        tomato-salad-food tomato-lettuce-salad-food tomato-lettuce-onion-salad-food carrot-banana-food mashed-carrot-banana-food cucumber-onion-food apple-watermelon-food - food-tag ; food names

        )

    ;;--------------------------------------------------------------------
    ;; Predicates
    ;;--------------------------------------------------------------------
    (:predicates
        (clear ?l - location) ; whether location is empty
        (on ?s - static-object ?l - location) ; static object is at location
        (at ?d - dynamic-object ?l - location) ; dynamic object is at location (movable)
        (move-dir ?lf - location ?lt - location ?dir - direction) ; adjacent location and how to get there
        (holding ?ag - agent ?x -
            (either plate ingredient)) ; agent holds item
        (handempty ?ag - agent)
        (on-plate ?i - ingredient ?p - plate) ; ingredient is on plate
        (isfood ?p - plate ?f - food-tag) ; plate can be viewed as a food of a certain type
        (served ?p - plate) ; plate has been served
        (get-chopped ?i -
            (either chop-ingredient chop-smash-ingredient)) ; whether ingredient is chopped
        (get-smashed ?i -
            (either smash-ingredient chop-smash-ingredient)) ; whether ingredient is smashed
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
            (imply (is-block ?to) (not (block-on ?to))) ; if the destination is a block, it must not be on the block
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

)
    ;; ------------------------------------------------ Pick an item lying at the same tile
    (:action pick-up
    :parameters (?ag - agent ?it - (either ingredient plate) ?agloc ?itemloc - location ?dir - direcction)
    :precondition (and
        (at ?ag ?agloc)
        (at ?it ?itemloc)
        (move-dir ?agloc ?itemloc ?dir) ; agent can reach the item
        )
    :effect (and 
        
        )
    )

;     ;; ------------------------------------------------ Put the held item down on the current tile
;     (:action put-down
;         :parameters (?ag - agent ?it - item ?loc - location)
;         :precondition (and (holding ?ag ?it)
;             (at-agent ?ag ?loc)
;             (clear ?loc))
;         :effect (and (at ?it ?loc)
;             (handempty ?ag)
;             (not (holding ?ag ?it)))
;     )

;     ;; ------------------------------------------------ Place food on a Cutboard (appliance)
;     (:action place-on-cutboard
;         :parameters (?ag - agent ?f - food ?cb - appliance ?loc - location)
;         :precondition (and (holding ?ag ?f)
;             (at-agent ?ag ?loc)
;             (at ?cb ?loc))
;         :effect (and (at ?f ?loc)
;             (handempty ?ag)
;             (not (holding ?ag ?f))
;             ;; conditional: board becomes ready only for fresh food
;             (when
;                 (not (chopped ?f))
;                 (ready ?cb)))
;     )

;     ;; ------------------------------------------------ Chop the food that is on the (ready) Cutboard
;     (:action chop
;         :parameters (?ag - agent ?f - food ?cb - appliance ?loc - location)
;         :precondition (and (at-agent ?ag ?loc)
;             (at ?cb ?loc)
;             (ready ?cb)
;             (at ?f ?loc)
;             (not (chopped ?f)))
;         :effect (and (chopped ?f)
;             (not (ready ?cb)))
;     ) ; board now used

;     ;; ------------------------------------------------ Deliver: put item on delivery square (= container)
;     (:action deliver
;         :parameters (?ag - agent ?it - item ?dsq - container ?loc - location)
;         :precondition (and (holding ?ag ?it)
;             (at ?dsq ?loc)
;             (at-agent ?ag ?loc))
;         :effect (and (on ?it ?dsq)
;             (handempty ?ag)
;             (not (holding ?ag ?it)))
;     )
; )