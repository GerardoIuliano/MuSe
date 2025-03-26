const Mutation = require('../../mutation');

function REOperator() {
  this.ID = "RE";
  this.name = "reentrancy";
}

REOperator.prototype.getMutations = function(file, source, visit) {
  const mutations = [];
  const mappings = new Set(); // Memorizza i mapping dichiarati nel contratto

  // Identifica le dichiarazioni di mapping per tenere traccia delle variabili di tipo mapping
  visit({
    StateVariableDeclaration: (node) => {
      node.variables.forEach((variable) => {
        if (variable.typeName.type === "Mapping" &&
            variable.typeName.keyType.name === "address" &&
            variable.typeName.valueType.name &&
            variable.typeName.valueType.name.includes("uint")
        ){
              mappings.add(variable.name); // Aggiungi il nome della variabile mapping
        }
      });
    }
  });

  // Helper per identificare l'assegnazione a un mapping, es. balances[msg.sender] = <valore>;
  function isMappingAssignment(stmt) {
    if (stmt.type !== "ExpressionStatement" || stmt.expression.type !== "BinaryOperation" || stmt.expression.operator === "+=") return false;

    const left = stmt.expression.left;
    const right = stmt.expression.right;

    isAddition = right.type === "BinaryOperation" && right.operator === "+";
    //console.log(mappings.has(left.base.name))

    // Verifica che l'accesso sia del tipo mapping[msg.sender] e che la variabile sia un mapping
    return left.type === "IndexAccess" &&
           left.index &&
           left.index.type === "MemberAccess" &&
           left.index.memberName === "sender" &&
           mappings.has(left.base.name) && // Verifica che la variabile sia un mapping dichiarato
           !isAddition;
  }

  // Helper per identificare la chiamata esterna, es. msg.sender.call(...);
  function isExternalCall(stmt) {
    if (stmt.type !== "VariableDeclarationStatement" || stmt.initialValue.type !== "FunctionCall") return false;
    const callExpr = stmt.initialValue.expression.expression;

    return callExpr &&
           callExpr.type === "MemberAccess" &&
           ((callExpr.memberName === "call" &&
           callExpr.expression &&
           callExpr.expression.memberName === "sender") ||
           (callExpr.expression.memberName === "call" &&
           callExpr.expression.expression &&
           callExpr.expression.expression.memberName === "sender"));
  }

  visit({
    FunctionDefinition: (node) => {
      if (!node.body || !node.body.statements) return;

      let assignmentStmt = null;
      let callStmt = null;
      let assignmentIndex = null;

      node.body.statements.forEach((stmt, index) => {
        if (isMappingAssignment(stmt)) {
          assignmentStmt = stmt;
          assignmentIndex = index;
        }
        if (assignmentStmt && !callStmt && isExternalCall(stmt)) {
          callStmt = stmt;
        }
      });

      if (assignmentStmt && callStmt && assignmentIndex !== null) {
        const mutationStart = assignmentStmt.range[0];
        const mutationEnd = callStmt.range[1] + 1;

        const assignmentCode = source.slice(assignmentStmt.range[0], assignmentStmt.range[1] + 1);
        const callCode = source.slice(callStmt.range[0], callStmt.range[1] + 1);

        // Genera il codice mutato: sposta l'aggiornamento dello stato dopo la chiamata esterna
        const mutatedCode = callCode + "\n" + assignmentCode;
        const startLine = assignmentStmt.loc.start.line;
        const endLine = callStmt.loc.end.line;

        mutations.push(
          new Mutation(file, mutationStart, mutationEnd, startLine, endLine, source.slice(mutationStart, mutationEnd), mutatedCode, this.ID)
        );
      }
    }
  });

  return mutations;
};

module.exports = REOperator;
