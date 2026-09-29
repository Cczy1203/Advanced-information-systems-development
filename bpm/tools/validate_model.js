// Parse the model the way Camunda Modeler does and report what its status bar
// would show as a problem.
//
// bpmn-moddle is the parser underneath the Modeler; the Zeebe descriptor adds
// the zeebe: extension elements, without which every form and candidate group
// would look like an unknown element rather than a missing one.
//
// Usage:  node tools/validate_model.js model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn
// Needs bpmn-moddle and zeebe-bpmn-moddle resolvable from the working directory.

const fs = require('fs');
const path = require('path');

// bpmn-moddle is not vendored here, so allow the caller to point at wherever it
// is installed.  NODE_MODULES_DIR wins; otherwise we look beside this file.
if (process.env.NODE_MODULES_DIR) {
  module.paths.unshift(process.env.NODE_MODULES_DIR);
  module.paths.unshift(path.join(process.env.NODE_MODULES_DIR, '..'));
}

const bpmnPath = process.argv[2];
if (!bpmnPath) {
  console.error('usage: node validate_model.js <file.bpmn>');
  console.error('       NODE_MODULES_DIR=/path/to/node_modules node validate_model.js <file.bpmn>');
  process.exit(2);
}
const xml = fs.readFileSync(bpmnPath, 'utf8');

const BpmnModdle = require('bpmn-moddle').BpmnModdle;
const zeebeDescriptor = JSON.parse(fs.readFileSync(
  require.resolve('zeebe-bpmn-moddle/resources/zeebe.json'), 'utf8'));
const moddle = new BpmnModdle({ zeebe: zeebeDescriptor });

moddle.fromXML(xml)
  .then(({ rootElement, warnings, references }) => {
    console.log('parse warnings      :', warnings.length);
    warnings.slice(0, 12).forEach(w => console.log('   W:', w.message));

    const unresolved = (references || []).filter(r => !r.element);
    console.log('unresolved refs     :', unresolved.length);
    unresolved.slice(0, 8).forEach(r => console.log('   U:', r.property, r.id));

    const root = rootElement.rootElements;
    const collab = root.find(e => e.$type === 'bpmn:Collaboration');
    const procs = root.filter(e => e.$type === 'bpmn:Process');
    console.log('participants        :', collab ? collab.participants.length : 0);
    console.log('processes           :', procs.length,
                '| executable:', procs.filter(p => p.isExecutable).length);

    let dangling = 0, noForm = 0, noGroup = 0, noType = 0;
    procs.forEach(p => {
      const ids = new Set((p.flowElements || []).map(f => f.id));
      (p.flowElements || []).forEach(f => {
        const t = f.$type;
        if (t === 'bpmn:SequenceFlow') {
          if (!f.sourceRef || !ids.has(f.sourceRef.id)) dangling++;
          if (!f.targetRef || !ids.has(f.targetRef.id)) dangling++;
        }
        const ext = (f.extensionElements && f.extensionElements.values) || [];
        if (t === 'bpmn:UserTask') {
          const fd = ext.find(e => e.$type === 'zeebe:FormDefinition');
          const ad = ext.find(e => e.$type === 'zeebe:AssignmentDefinition');
          if (!fd || !fd.formId) noForm++;
          if (!ad || !ad.candidateGroups) noGroup++;
        }
        if (t === 'bpmn:ServiceTask') {
          const td = ext.find(e => e.$type === 'zeebe:TaskDefinition');
          if (!td || !td.type) noType++;
        }
      });
    });
    console.log('dangling seq refs   :', dangling);
    console.log('user tasks no form  :', noForm);
    console.log('user tasks no group :', noGroup);
    console.log('service tasks no job type:', noType);

    const clean = warnings.length === 0 && unresolved.length === 0 && dangling === 0
      && noForm === 0 && noGroup === 0 && noType === 0;
    console.log(clean
      ? 'RESULT: clean - Modeler would report no problems'
      : 'RESULT: problems found');
    process.exit(clean ? 0 : 1);
  })
  .catch(e => {
    console.log('PARSE FAILED:', e.message);
    process.exit(1);
  });
