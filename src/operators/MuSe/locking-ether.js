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

  visit({
    ContractDefinition: (contractNode) => {
      //console.log(contractNode)
      // Verifica se il contratto è valido per le mutazioni:
      // - Deve essere di tipo "contract"
      // - Non deve essere astratto (abstract)
      if (contractNode && contractNode.kind !== "contract") {
        return;
      }

      // Processa tutte le definizioni di funzioni (subNodes) all'interno del contratto
      contractNode.subNodes.forEach((subNode) => {
        if (subNode.type === "FunctionDefinition") {
          // Salta i costruttori
          if (subNode.isConstructor) {
            return;
          }

          let containsTargetStatement = false;
          // Assicurati che il corpo della funzione sia un blocco contenente statement
          if (subNode.body && subNode.body.type === "Block" && Array.isArray(subNode.body.statements)) {
            for (const statement of subNode.body.statements) {
              // Esamina gli statement di livello top: ad esempio ExpressionStatement
              if (statement.type === "ExpressionStatement" &&
                  statement.expression &&
                  statement.expression.type === "FunctionCall") {
                const callee = statement.expression.expression;
                if (callee) {
                  if (callee.type === "Identifier" && targetMethods.includes(callee.name)) {
                    containsTargetStatement = true;
                    break;
                  }
                  if (callee.type === "MemberAccess" && targetMethods.includes(callee.memberName)) {
                    containsTargetStatement = true;
                    break;
                  }
                }
              }
              // Gestione delle chiamate ai target dentro dichiarazioni di variabili
              if (statement.type === "VariableDeclarationStatement" &&
                  statement.initialValue &&
                  statement.initialValue.type === "FunctionCall") {
                const callee = statement.initialValue.expression.expression;
                if (callee) {
                  if (callee.type === "Identifier" && targetMethods.includes(callee.name)) {
                    containsTargetStatement = true;
                    break;
                  }
                  if (callee.type === "MemberAccess" && targetMethods.includes(callee.memberName)) {
                    containsTargetStatement = true;
                    break;
                  }
                }
              }
            }
          }

          if (containsTargetStatement) {
            // Se la funzione contiene almeno uno statement che richiama un metodo target,
            // genera una mutation che elimina l'intera funzione (definizione e corpo).
            mutations.push(new Mutation(
              file,
              subNode.range[0],
              subNode.range[1] + 1,
              subNode.loc.start.line,
              subNode.loc.end.line,
              source.slice(subNode.range[0], subNode.range[1] + 1),
              "", // La funzione viene eliminata sostituendo il codice con una stringa vuota.
              operator.ID
            ));
          }
        }
      });
    }
  });

  return mutations;
};

module.exports = LEOperator;
