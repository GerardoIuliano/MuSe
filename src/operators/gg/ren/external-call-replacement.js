const Mutation = require('../../../mutation');

function ECROperator() {
  this.ID = "ECR";
  this.name = "external-call-replacement";
}

ECROperator.prototype.getMutations = function(file, source, visit) {
  const mutations = [];
  
  visit({
    FunctionCall: (node) => {
      if (node.expression.type === "MemberAccess" && node.expression.expression.type === "Identifier") {
        const functionName = node.expression.memberName;
        
        if (functionName === "call" || functionName === "delegatecall" || functionName === "staticcall") {
          const start = node.range[0];
          const end = node.range[1];
          const startLine = node.loc.start.line;
          const endLine = node.loc.end.line;

          const original = source.slice(start, end);

          let replacement;
          if (functionName === "call") {
            replacement = `${node.expression.expression.name}.call{value: 0, gas: 10000}("")`;
          } else if (functionName === "delegatecall") {
            replacement = `${node.expression.expression.name}.delegatecall(abi.encodeWithSignature("fallback()"))`;
          } else if (functionName === "staticcall") {
            replacement = `${node.expression.expression.name}.staticcall("")`;
          }

          mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
        }
      }
    }
  });

  return mutations;
};

module.exports = ECROperator;
