const Mutation = require('../../mutation');

function LEOperator() {
  this.ID = "LE";
  this.name = "locking-ether";
}

LEOperator.prototype.getMutations = function(file, source, visit) {
  const mutations = [];
  const targetMethods = ["send", "transfer", "call", "staticcall", "delegatecall", "callcode", "selfdestruct"];


  visit({
    FunctionDefinition: (node) => {
      // Salta eventuali costruttori
      if (node.isConstructor) {
        return;
      }

      let containsTargetStatement = false;
      // Assicurati che il corpo della funzione sia un blocco contenente statement
      if (node.body && node.body.type === "Block" && Array.isArray(node.body.statements)) {
        for (const statement of node.body.statements) {
          // Considera solamente gli statement di livello top: ad es. ExpressionStatement
          if (statement.type === "ExpressionStatement" && statement.expression && statement.expression.type === "FunctionCall") {
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
          if(statement.type === "VariableDeclarationStatement" && statement.initialValue && statement.initialValue.type === "FunctionCall") {
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
          node.range[0],
          node.range[1] + 1,
          node.loc.start.line,
          node.loc.end.line,
          source.slice(node.range[0], node.range[1] + 1),
          "", // La funzione viene eliminata sostituendo il codice con una stringa vuota.
          this.ID
        ));
      }
    }
  });

  return mutations;
};

module.exports = LEOperator;
