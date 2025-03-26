const Mutation = require('../../mutation');

/**
 * TimestampDependence is a mutation testing operator designed to replace time-dependent
 * variables in comparisons with a constant representing a time less than 20 seconds.
 *
 * **Purpose**:
 * The operator targets occurrences of comparisons like `block.timestamp < variable` or `now < variable`.
 * It replaces the variable (the non-time-reference side) with a constant (e.g., 15 seconds) to test how such changes
 * affect contract behavior and security.
 *
 * **How It Works**:
 * 1. **Identify Time-based Comparisons**: The script looks for binary operations where the operator is `<`, `<=`, `>` or `>=`
 *    and either the left-hand side or the right-hand side is a time reference (`block.timestamp` or `now`).
 * 2. **Perform Replacement**: When such a pattern is detected and the opposite side is a variable (an Identifier),
 *    it replaces that variable with the constant "15 seconds", representing a time value less than 20 seconds.
 * 3. **Create Mutation Instances**: It creates and records a mutation reflecting this replacement.
 * 4. **Return Mutations**: The list of mutations is then returned for further testing and analysis.
 */

function TDOperator() {
  this.ID = "TD";
  this.name = "timestamp-dependence";
}

TDOperator.prototype.getMutations = function(file, source, visit) {
  const mutations = [];
  // Constant to substitute, representing a time value under 20 seconds.
  const constantReplacement = "15 seconds";

  // Helper function to check if a node represents a time reference.
  function isTimeReference(node) {
    // Check for block.timestamp: a MemberAccess with member "timestamp" on an Identifier "block"
    if (
      node.type === "MemberAccess" &&
      node.memberName === "timestamp" &&
      node.expression &&
      node.expression.type === "Identifier" &&
      node.expression.name === "block"
    ) {
      return true;
    }
    // Check if the node is the identifier "now"
    if (node.type === "Identifier" && node.name === "now") {
      return true;
    }
    return false;
  }

  visit({
    BinaryOperation: (node) => {
      // Check for the operators: <, <=, >, >=
      if (
        node.operator === "<" ||
        node.operator === "<=" ||
        node.operator === ">" ||
        node.operator === ">="
      ) {
        // Case 1: Time reference is on the left and the right-hand side is a variable (Identifier)
        if (isTimeReference(node.left) && node.right.type === "Identifier") {
          const start = node.right.range[0];
          const end = node.right.range[1] + 1;
          const startLine = node.right.loc.start.line;
          const endLine = node.right.loc.end.line;
          const original = source.slice(start, end);

          mutations.push(
            new Mutation(file, start, end, startLine, endLine, original, constantReplacement, this.ID)
          );
        }
        // Case 2: Time reference is on the right and the left-hand side is a variable (Identifier)
        if (isTimeReference(node.right) && node.left.type === "Identifier") {
          const start = node.left.range[0];
          const end = node.left.range[1] + 1;
          const startLine = node.left.loc.start.line;
          const endLine = node.left.loc.end.line;
          const original = source.slice(start, end);

          mutations.push(
            new Mutation(file, start, end, startLine, endLine, original, constantReplacement, this.ID)
          );
        }
      }
    }
  });

  return mutations;
};

module.exports = TDOperator;
