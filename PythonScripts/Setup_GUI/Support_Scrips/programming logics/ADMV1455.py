def logic(client):
    """Custom logic for ADMV1455."""
    client.AddByComponentId("ADMV1455Board")
    client.ContextPath = "\System\Subsystem_1\ADMV1455 Board\ADMV1455"
    client.NavigateToPath("Root::System.Subsystem_1.ADMV1455 Board.ADMV1455")
    client.Run ("@Reset")
    client.Run("@BB_LB_Init")
