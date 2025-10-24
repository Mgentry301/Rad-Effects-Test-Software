def logic(client):
    client.AddByComponentId("ADMV1355Board")
    client.ContextPath = "\System\Subsystem_1\ADMV1355 Board\ADMV1355"
    client.NavigateToPath("Root::System.Subsystem_1.ADMV1355 Board.ADMV1355")
    client.Run("@Reset")
