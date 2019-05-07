import re

import z3


def parse_smt2_file(smt2_filename):
    """Reads a smt2 file and returns the first formula.

    Args:
        smt2_filename: smt2 file that was generated from Sketch.

    Raises:
        An assertion if the original smt2 file didn't contain any assert
        statements.
    """
    # parse_smt2_file returns a vector of ASTs, and each element corresponds to
    # one assert statement in the original file. The smt2 file generated by
    # sketch only has one assertions, simply take the first.
    formulas = z3.parse_smt2_file(smt2_filename)
    assert len(formulas) == 1, (smt2_filename,
                                'contains 0 or more than 1 asserts.')
    return formulas[0]


def negated_body(formula):
    """Given a z3.QuantiferRef formula with z3.Int variables,
    return negation of the body.

    Returns:
        A z3.BoolRef which is the negation of the formula body.
    """
    assert z3.is_quantifier(
        formula), ('Formula is not a quantifier:\n', formula)
    var_names = [formula.var_name(i) for i in range(formula.num_vars())]
    vs = [z3.Int(n) for n in var_names]
    return z3.Not(z3.substitute_vars(formula.body(), *reversed(vs)))


def generate_counter_examples(smt2_filename):
    """Given a smt2 file that was generated from sketch, returns counterexample
    values for input packet fields and state group variables.

    Returns:
        A tuple of two dicts from string to ints, where the first one
        represents counterexamples for packet variables and the second for
        state group variables.
    """
    formula = parse_smt2_file(smt2_filename)
    new_formula = negated_body(formula)

    z3_slv = z3.Solver()
    z3_slv.set(proof=True, unsat_core=True)
    z3_slv.add(new_formula)

    pkt_fields = {}
    state_vars = {}

    result = z3_slv.check()
    if result != z3.sat:
        print('Failed to generate counterexamples, z3 returned', result)
        return (pkt_fields, state_vars)

    model = z3_slv.model()
    for var in model.decls():
        # The variable names used by sketch have trailing _\d+_\d+_\d+ pattern,
        # need to remove them to get original variable names.
        var_name = re.sub(r'_\d+_\d+_\d+$', '', var.name(), count=1)
        value = model.get_interp(var).as_long()
        if var_name.startswith('pkt_'):
            pkt_fields[var_name] = value
        elif var_name.startswith('state_group_'):
            state_vars[var_name] = value

    return (pkt_fields, state_vars)


def simple_check(smt2_filename):
    """Given a smt2 file generated from a sketch, parses assertion from the
    file and checks with z3. We assume that the file already has input bit
    ranges defined by sketch.

    Returns:
        True if satisfiable else False.
    """
    formula = parse_smt2_file(smt2_filename)

    # The original formula's body is comprised of Implies(A, B) where A
    # specifies range of input variables and where B is a condition. We're
    # interested to check whether B is True within the range specified by A

    z3_slv = z3.Solver()
    z3_slv.add(formula)

    return z3_slv.check() == z3.sat