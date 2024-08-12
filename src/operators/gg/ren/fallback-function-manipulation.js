const Mutation = require('../../../mutation');

function FFMOperator() {
  this.ID = "FFM";
  this.name = "fallback-function-manipulation";
}

FFMOperator.prototype.getMutations = function(file, source, visit) {
  const mutations = [];
  
  visit({
    FunctionDefinition: (node) => {
      // Only target fallback functions
      if (node.kind === "fallback" || node.kind === "receive") {
        const start = node.body.range[0] + 1; // Insert inside the function body
        const end = node.body.range[0] + 1;
        const startLine = node.body.loc.start.line;
        const endLine = node.body.loc.start.line;

        // External call to an example function `externalFunction()`
        const externalCall = `address(this).call("");`;
        const original = "";
        const replacement = externalCall;

        mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
      }
    }
  });

  return mutations;
};

module.exports = FFMOperator;
