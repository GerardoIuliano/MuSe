// mutation_operators/TDOperator.js

const Mutation = require('../../mutation'); // Adjust path if necessary

/**
 * TDOperator (Timestamp Dependency Operator) is a mutation testing operator for Solidity.
 *
 * **Purpose**:
 * This operator targets all occurrences of accesses to block properties (like block.number,
 * block.difficulty, block.coinbase, block.gaslimit, etc.) within the contract code.
 * It replaces these accesses with `block.timestamp`. This helps test the contract's
 * reliance on specific block properties versus relying solely on the timestamp, which
 * can have security implications (e.g., timestamp manipulation by miners).
 *
 * **How It Works**:
 * 1. **Identify Block Property Accesses**: The script traverses the Abstract Syntax Tree (AST)
 *    of the Solidity code, looking for `MemberAccess` nodes where the base expression
 *    is the identifier `block`.
 * 2. **Filter Out block.timestamp**: It specifically ignores occurrences of `block.timestamp` itself,
 *    as replacing it with itself is not a meaningful mutation.
 * 3. **Perform Replacements**: Each identified access to a block property (other than `block.timestamp`)
 *    is marked for replacement. The replacement value is always the string `"block.timestamp"`.
 * 4. **Create Mutation Instances**: For each identified location, it creates and records a `Mutation`
 *    object containing the file path, start/end position, start/end line number, the original
 *    code snippet (e.g., "block.number"), the replacement code ("block.timestamp"), and the
 *    operator ID ("TD").
 * 5. **Return Mutations**: The list of generated `Mutation` objects is returned for use in the
 *    mutation testing process.
 */
function TDOperator() {
  this.ID = "TD"; // Unique Identifier for this operator
  this.name = "timestamp-dependency"; // Descriptive name
}

/**
 * Generates mutations by replacing block property accesses with block.timestamp.
 * @param {string} file - The path to the Solidity file being mutated.
 * @param {string} source - The original source code of the Solidity file.
 * @param {function} visit - A function (likely from solidity-parser-antlr or similar)
 *                           that takes a visitor object to traverse the AST.
 * @returns {Mutation[]} - An array of Mutation objects representing the generated mutations.
 */
TDOperator.prototype.getMutations = function(file, source, visit) {
  const mutations = [];

  // Use the visitor pattern to traverse the AST
  visit({
    // Target nodes representing member access (like object.property or array[index])
    MemberAccess: (node) => {
      // Check if the access is on the 'block' global variable
      // node.expression is the part before the dot ('.')
      // node.memberName is the part after the dot ('.')
      if (node.expression.type === 'Identifier' && node.expression.name === 'block') {

        // We want to replace block.PROPERTY with block.timestamp.
        // We should NOT replace block.timestamp with block.timestamp.
        if (node.memberName !== 'timestamp') {
          // Get positional information from the AST node
          const start = node.range[0]; // Start character index
          const end = node.range[1] + 1; // End character index (exclusive)
          const startLine = node.loc.start.line; // Start line number
          const endLine = node.loc.end.line; // End line number
          const original = source.slice(start, end); // Extract the original code snippet
          const replacement = "block.timestamp"; // The code to replace it with

          // Create a new Mutation object and add it to the list
          mutations.push(
            new Mutation(
              file,         // File path
              start,        // Start character index
              end,          // End character index
              startLine,    // Start line
              endLine,      // End line
              original,     // Original code snippet (e.g., "block.number")
              replacement,  // Replacement code ("block.timestamp")
              this.ID       // Operator ID ("TD")
            )
          );
        }
      }
    }
  });

  // Return the collected mutations
  return mutations;
};

// Export the operator class
module.exports = TDOperator;