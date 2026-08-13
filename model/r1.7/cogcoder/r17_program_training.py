from __future__ import annotations
from .neural_system2 import NeuralSystem2Workspace

def latent_program_trainable_parameter_names(model:NeuralSystem2Workspace)->list[str]:
    names=[n for n,_ in model.named_parameters() if n.startswith("latent_program_ranker.")]
    if not names: raise ValueError("model exposes no latent_program_ranker parameters")
    return names

def latent_program_internal_gate(metrics:dict[str,object])->bool:
    if not float(metrics["candidate_operation_accuracy"])>float(metrics["baseline_operation_accuracy"]): return False
    if float(metrics["candidate_submit_accuracy"])<float(metrics["baseline_submit_accuracy"]): return False
    templates=metrics.get("templates",{})
    for row in templates.values():
        if float(row["candidate_operation_accuracy"])<float(row["baseline_operation_accuracy"]): return False
    return bool(templates)
