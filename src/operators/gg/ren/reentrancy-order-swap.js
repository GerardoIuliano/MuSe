const Mutation = require('../../../mutation');

function ROSOperator() {
    this.ID = "ROS";
    this.name = "reentrancy-order-swap";
}

ROSOperator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];

    visit({
        FunctionDeclaration: (node) => {
            const body = node.body.body;
            
            for (let i = 0; i < body.length - 1; i++) {
                const statement = body[i];
                const nextStatement = body[i + 1];
                
                const isStateChange = statement.type === "ExpressionStatement" && (
                    statement.expression.type === "AssignmentExpression" ||
                    statement.expression.type === "UpdateExpression"
                );
                
                const isExternalCall = nextStatement.type === "ExpressionStatement" &&
                    nextStatement.expression.type === "CallExpression" &&
                    nextStatement.expression.callee.type === "MemberExpression" &&
                    ["call", "delegatecall", "send"].includes(nextStatement.expression.callee.property.name);

                console.log(isStateChange)
                console.log(isExternalCall)
                if (isStateChange && isExternalCall) {

                    const startLine = statement.loc.start.line;
                    const endLine = nextStatement.loc.end.line;
                    const original = source.slice(statement.range[0], nextStatement.range[1]);

                    const swapped = source.slice(nextStatement.range[0], nextStatement.range[1]) + "\n" +
                        source.slice(statement.range[0], statement.range[1]);

                    const replacement = source.substring(0, statement.range[0]) + swapped + source.substring(nextStatement.range[1]);

                    mutations.push(new Mutation(file, statement.range[0], nextStatement.range[1], startLine, endLine, original, replacement, this.ID));
                }
            }
        }
    });

    return mutations;
};

module.exports = ROSOperator;
