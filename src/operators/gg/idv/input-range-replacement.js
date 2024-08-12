const Mutation = require('../../../mutation');

function IRROperator() {
    this.ID = "IRR";
    this.name = "input-range-replacement";
}

function getRandomReplacement(typeName) {
    if (typeName.name === "uint256") {
        return "uint256(keccak256(abi.encodePacked(block.timestamp, block.difficulty))) % 2 == 0 ? 0 : type(uint256).max;";
    } else if (typeName.name === "int256") {
        return "int256(uint256(keccak256(abi.encodePacked(block.timestamp, block.difficulty))) % 2 == 0 ? 0 : type(int256).max);";
    } else if (typeName.name === "uint") {
        return "uint(keccak256(abi.encodePacked(block.timestamp, block.difficulty))) % 2 == 0 ? 0 : type(uint).max;";
    } else if (typeName.name === "int") {
        return "int(uint256(keccak256(abi.encodePacked(block.timestamp, block.difficulty))) % 2 == 0 ? 0 : type(int).max);";
    } else return null;
}


IRROperator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];
    visit({
        FunctionDefinition: (node) => {
            if (node.body) {
                node.parameters.forEach(param => {
                    const start = param.range[0];
                    const end = param.range[1];
                    const startLine = param.loc.start.line;
                    const endLine = param.loc.end.line;
                    const original = source.slice(start, end);

                    const replacement = getRandomReplacement(param.typeName);
                    if (replacement) {
                        const mutatedCode = `${original} ${replacement}`;
                        mutations.push(new Mutation(file, start, end, startLine, endLine, original, mutatedCode, this.ID));
                    }
                });
            }
        }
    });
    return mutations;
};

module.exports = IRROperator;
