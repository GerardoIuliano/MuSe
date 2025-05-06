const Mutation = require('../../mutation');

function LEOperator() {
  this.ID = "LE";
  this.name = "locking-ether";
}

LEOperator.prototype.getMutations = function(file, source, visit) {
  const mutations = [];
  const targetMethods = [
    "send",
    "transfer",
    "call",
    "staticcall",
    "delegatecall",
    "callcode",
    "selfdestruct"
  ];
  const operator = this;

  const candidateFunctions = new Map(); // nome -> nodo
  const calledFunctions = new Set(); // Set dei nomi delle funzioni chiamate

  visit({
    ContractDefinition: (contractNode) => {
      if (contractNode && contractNode.kind !== "contract") return;

      // Prima passata: trova le funzioni che contengono targetMethods
      contractNode.subNodes.forEach((subNode) => {
        if (subNode.type === "FunctionDefinition" && !subNode.isConstructor && subNode.name) {
          let containsTarget = false;

          const checkStatements = (node) => {
            if (!node || typeof node !== 'object') return;

            if (node.type === "FunctionCall") {
              const callee = node.expression;
              if (callee) {
                if (callee.type === "Identifier" && targetMethods.includes(callee.name)) {
                  containsTarget = true;
                }
                if (callee.type === "MemberAccess" && targetMethods.includes(callee.memberName)) {
                  containsTarget = true;
                }
              }
            }

            for (const key in node) {
              const child = node[key];
              if (typeof child === 'object') {
                if (Array.isArray(child)) child.forEach(checkStatements);
                else checkStatements(child);
              }
            }
          };

          checkStatements(subNode.body);
          if (containsTarget) {
            candidateFunctions.set(subNode.name, subNode);
          }
        }
      });

      // Seconda passata: cerca se le candidate sono chiamate da altre funzioni
      const checkCalls = (node) => {
        if (!node || typeof node !== 'object') return;

        if (node.type === "FunctionCall" && node.expression?.type === "Identifier") {
          const calledName = node.expression.name;
          if (candidateFunctions.has(calledName)) {
            calledFunctions.add(calledName);
          }
        }

        for (const key in node) {
          const child = node[key];
          if (typeof child === 'object') {
            if (Array.isArray(child)) child.forEach(checkCalls);
            else checkCalls(child);
          }
        }
      };

      checkCalls(contractNode);

      // Terza passata: elimina solo le funzioni candidate non chiamate
      for (const [funcName, subNode] of candidateFunctions.entries()) {
        if (!calledFunctions.has(funcName)) {
          mutations.push(new Mutation(
            file,
            subNode.range[0],
            subNode.range[1] + 1,
            subNode.loc.start.line,
            subNode.loc.end.line,
            source.slice(subNode.range[0], subNode.range[1] + 1),
            "",
            operator.ID
          ));
        }
      }
    }
  });

  return mutations;
};

module.exports = LEOperator;
