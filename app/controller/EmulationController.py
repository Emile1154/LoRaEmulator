from model.Project import ProjectModel


class EmulationController:
    def __init__(self, project_model: ProjectModel):
        self.project = project_model
        self.running = False

    def start(self):
        if self.running:
            return
        self.running = True
        print("Emulation started")
        for node in self.project.nodes:
            print(f"Start node {node.local_port} -> {node.remote_port}")

    def stop(self):
        if not self.running:
            return
        self.running = False
        print("Emulation stopped")
