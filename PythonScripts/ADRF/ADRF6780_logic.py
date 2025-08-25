def logic(client):
    """Custom logic for ADRF6780."""
    client.ContextPath = "\System\Subsystem_1\ADRF6780-042654 RevA\ADRF6780"
    client.SetBoolParameter("IQ_Mode_Enable", "False", "-1")
    client.SetBoolParameter("IF_Mode_Enable", "True", "-1")
    client.Run("@ApplySettings")
    client.ReadRegister("0")
    client.ReadRegister("3")
    client.ReadRegister("6")
    client.Run("@ReadSettings")
    print("Custom logic for ADRF6780 executed.")