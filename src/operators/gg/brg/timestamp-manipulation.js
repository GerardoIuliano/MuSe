const Mutation = require('../../../mutation');

function TMOperator() {
    this.ID = "TM";
    this.name = "timestamp-manipulation";
}

function getManipulatedTimestamp() {
    return "uint256(keccak256(abi.encodePacked(block.timestamp))) % 2 == 0 ? 0 : type(uint256).max";
}

TMOperator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];
    visit({
        MemberAccess: (node) => {
            if (node.memberName === "timestamp" && node.expression.name === "block") {
                const start = node.range[0];
                const end = node.range[1];
                const startLine = node.loc.start.line;
                const endLine = node.loc.end.line;
                const original = source.slice(start, end);
                
                const replacement = getManipulatedTimestamp();
                mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
            }
        }
    });
    return mutations;
};

module.exports = TMOperator;
