const Mutation = require('../../../mutation');

function RFCOperator() {
  this.ID = "RFC";
  this.name = "reentrant-function-call";
}

RFCOperator.prototype.getMutations = function(file, source, visit) {
  const mutations = [];
  
  visit({
    FunctionDefinition: (node) => {
      // Only target public functions
      if (node.visibility === "public") {
        const functionName = node.name;
        
        if (functionName) {
          const start = node.body.range[0] + 1; // Insert inside the function body
          const end = node.body.range[0] + 1;
          const startLine = node.body.loc.start.line;
          const endLine = node.body.loc.start.line;

          const recursiveCall = `${functionName}();`;
          const original = "";
          const replacement = recursiveCall;

          mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
        }
      }
    }
  });

  return mutations;
};

module.exports = RFCOperator;
