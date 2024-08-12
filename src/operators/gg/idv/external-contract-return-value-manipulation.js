const Mutation = require('../../../mutation');

function ECRVMOperator() {
  this.ID = "ECRVM";
  this.name = "external-contract-return-value-manipulation";
}

ECRVMOperator.prototype.getMutations = function(file, source, visit) {
  const mutations = [];
  
  visit({
    CallExpression: (node) => {
      // Check if the call is to an external contract
      if (node.callee.type === 'MemberExpression' && ['call', 'delegatecall', 'staticcall'].includes(node.callee.property.name)) {
        const start = node.range[0];
        const end = node.range[1];
        const startLine = node.loc.start.line;
        const endLine = node.loc.end.line;
        const original = source.slice(start, end);
        
        // Create a random return value
        const randomReturnValue = generateRandomValue();
        
        // Replace the call with a random return value
        const replacement = original.replace(/(call|delegatecall|staticcall)\(([^)]*)\)/g, (match) => {
          return `(${randomReturnValue})`; // Replace with random value
        });
        
        mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
      }
    }
  });

  return mutations;
};

// Helper function to generate a random return value
function generateRandomValue() {
  const types = ["uint256", "int256", "address", "bytes32"];
  const randomType = types[Math.floor(Math.random() * types.length)];
  
  switch (randomType) {
    case "uint256":
      return `uint256(${Math.floor(Math.random() * Number.MAX_SAFE_INTEGER)})`;
    case "int256":
      return `int256(${Math.floor(Math.random() * Number.MAX_SAFE_INTEGER) - Math.floor(Math.random() * Number.MAX_SAFE_INTEGER)})`;
    case "address":
      return `address(0x${Math.floor(Math.random() * 1e16).toString(16)})`;
    case "bytes32":
      return `bytes32(0x${Math.random().toString(16).padStart(64, '0')})`;
    default:
      return '0';
  }
}

module.exports = ECRVMOperator;
