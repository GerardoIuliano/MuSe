const Mutation = require('../../../mutation');

function NVIOperator() {
  this.ID = "NVI";
  this.name = "null-value-insertion";
}

NVIOperator.prototype.getMutations = function(file, source, visit) {
  const mutations = [];
  
  visit({
    FunctionDefinition: (node) => {
      // Directly access the parameters array
      const params = node.parameters;

      // Check if there are parameters to iterate over
      if (params && Array.isArray(params)) {
        params.forEach((param) => {
          const start = param.range[0];
          const end = param.range[1];
          const startLine = param.loc.start.line;
          const endLine = param.loc.end.line;
          const original = source.slice(start, end);
          
          let replacement;
          
          // Determine the replacement value based on the parameter type
          if (param.typeName.name === "uint256" || param.typeName.name === "int256" || param.typeName.name === "uint" || param.typeName.name === "int") {
            replacement = "0";
          } else if (param.typeName.name === "address") {
            replacement = "address(0)";
          } else if (param.typeName.name === "bool") {
            replacement = "false";
          } else if (param.typeName.type === "ArrayTypeName" || param.typeName.type === "Mapping") {
            replacement = "[]";
          } else if (param.typeName.type === "UserDefinedTypeName") {
            replacement = "0"; // Assume it's a struct with a default value of 0 for simplicity
          } else {
            replacement = "''"; // For string or other types
          }

          const replacementString = source.slice(0, start) + replacement + source.slice(end);

          mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacementString, this.ID));
        });
      }
    }
  });

  return mutations;
};

module.exports = NVIOperator;
