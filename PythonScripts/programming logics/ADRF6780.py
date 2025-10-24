def logic(client):
    client.ContextPath = "\System\Subsystem_1\ADRF6780-042654 RevA\ADRF6780"
    client.NavigateToPath("Root::System.Subsystem_1.ADRF6780-042654 RevA.ADRF6780")
    client.Run("@Reset")
    client.SetBoolParameter("IQ_Mode_Enable", "False", "-1")
    client.SetBoolParameter("IF_Mode_Enable", "True", "-1")
    client.Run("@ApplySettings")