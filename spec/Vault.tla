---- MODULE Vault ----
\* Formal model of HyperNexus VRL-1 vault state invariants:
\*   register (disjoint rings, unique tenant ids)
\*   persist  (atomic snapshot with a valid signature)
\*   reload   (only applies a validly-signed snapshot)
EXTENDS Naturals, FiniteSets

CONSTANTS
    TenantIds,   \* finite set of possible tenant ids
    RingEnds     \* finite set of ring endpoint values

VARIABLES
    tenants,     \* set of records [id |-> _, lo |-> _, hi |-> _]
    disk         \* [ok |-> BOOLEAN, tenants |-> set-of-records]

vars == <<tenants, disk>>

ValidRing(lo, hi) == lo < hi

Overlaps(a, b) == a.lo < b.hi /\ b.lo < a.hi

Init ==
    /\ tenants = {}
    /\ disk = [ok |-> FALSE, tenants |-> {}]

\* Register a tenant: unique id and disjoint (non-overlapping) ring required.
Register(id, lo, hi) ==
    /\ ValidRing(lo, hi)
    /\ id \notin {t.id : t \in tenants}
    /\ \A t \in tenants : ~ Overlaps([lo |-> lo, hi |-> hi], t)
    /\ tenants' = tenants \cup {[id |-> id, lo |-> lo, hi |-> hi]}
    /\ UNCHANGED disk

\* Persist: atomically write the current tenants with a valid signature.
Persist ==
    /\ disk' = [ok |-> TRUE, tenants |-> tenants]
    /\ UNCHANGED tenants

\* Tamper: an adversary invalidates the on-disk signature (rollback/forgery).
Tamper ==
    /\ disk' = [ok |-> FALSE, tenants |-> disk.tenants]
    /\ UNCHANGED tenants

\* Reload: only allowed from a validly-signed disk.
Reload ==
    /\ disk.ok = TRUE
    /\ tenants' = disk.tenants
    /\ UNCHANGED disk

RegisterNext ==
    \E id \in TenantIds, lo \in RingEnds, hi \in RingEnds : Register(id, lo, hi)

Next == RegisterNext \/ Persist \/ Tamper \/ Reload

Spec == Init /\ [][Next]_vars

\* Ring invariants: unique tenant ids and pairwise-disjoint rings.
NoDup == Cardinality({t.id : t \in tenants}) = Cardinality(tenants)

NoOverlap == \A a \in tenants, b \in tenants : a # b => ~ Overlaps(a, b)

\* Liveness/safety of reload: a forged disk is never reloaded.
ReloadOnlyWhenValid == [](disk.ok = FALSE => ~ ENABLED Reload)

====
