#!/usr/bin/env python

import numpy
from ortools.linear_solver import pywraplp

N = NUM_PROPOSALS = 100
M = NUM_REVIEWERS = 75
K = NUM_SUBJECTS = 25
NP = 3  # Min proposal coverage (reviews/proposal)
NR = 5  # Max reviewer workload

R = REVIEWERS = [list(numpy.random.choice([0, 1], p=[0.75, 0.25], size=K)) for l in range(M)]
P = PROPOSALS = [list(numpy.random.choice([0, 1], p=[0.9, 0.1], size=K)) for i in range(N)]
C = CONFLICTS = [list(numpy.random.choice([0, 1], p=[0.01, 0.99], size=M)) for i in range(N)]


def get_reviewer(i):
    return 'Reviewer #{:3d} exp={}'.format(i, ['{:3d}'.format(r) for r, v in enumerate(R[i]) if v])


def get_proposal(i):
    return 'Proposal #{:3d} req={}'.format(i, ['{:3d}'.format(p) for p, v in enumerate(P[i]) if v])


def main():
    # Create the solver and objective
    # solver = pywraplp.Solver("CMACRASolver", pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)
    solver = pywraplp.Solver("CMACRASolver", pywraplp.Solver.GLOP_LINEAR_PROGRAMMING)
    # solver = pywraplp.Solver("CMACRASolver", pywraplp.Solver.CLP_LINEAR_PROGRAMMING)

    X = [[solver.IntVar(0, 1, "M[{},{}]".format(i, j)) for j in range(M)] for i in range(N)]
    t = [[solver.IntVar(0, NP, "t[{},{}]".format(i, j)) for j in range(K)] for i in range(N)]
    all_t = [v for Vs in t for v in Vs]
    benefit = solver.Sum(all_t)

    # C3 - Proposal Coverage constraints
    for i in range(N):
        # solver.Add(solver.Sum([X[i][j] for j in range(M)]) >= NP) #  coverage greater than or equal to NP
        solver.Add(solver.Sum([X[i][j] for j in range(M)]) == NP)  # coverage equal to NP

    # C4 - Reviewer workload constraints
    for j in range(M):
        solver.Add(solver.Sum([X[i][j] for i in range(N)]) <= NR)

    # C5 - main objective constraints
    for i in range(N):
        for j in range(K):
            solver.Add(solver.Sum([R[l][j] * X[i][l] for l in range(M)]) >= P[i][j])

    # C6 - Conflict of Interests constraints
    for i in range(N):
        for j in range(M):
            if not C[i][j]:
                solver.Add(X[i][j] == 0)

    # solution and search
    objective = solver.Maximize(benefit)
    status = solver.Solve()

    for i in range(N):
        allocation = sum([X[i][j].SolutionValue() for j in range(M) if X[i][j].SolutionValue()])
        print("{}: {}, Reviewers = {}".format(
            get_proposal(i),
            allocation,
            [j for j in range(M) if X[i][j].SolutionValue()],
        ))
    print()
    for j in range(M):
        allocation = sum([X[i][j].SolutionValue() for i in range(N) if X[i][j].SolutionValue()])
        if not allocation: continue
        print("{}: {}, Proposals = {}".format(
            get_reviewer(j),
            allocation,
            [i for i in range(N) if X[i][j].SolutionValue()],
        ))
    print()
    print("Objective : %0.2f" % solver.Objective().Value())
    print("Duration  :", solver.WallTime(), "ms")
    if status == solver.OPTIMAL:
        print("Optimal Solution")
    elif status == solver.FEASIBLE:
        print("Feasible Solution")
    else:
        print("No Solution!")


if __name__ == "__main__":
    main()
