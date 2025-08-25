def logic(client):
    """Custom logic for ADMV1013."""
    client.ContextPath = "\System\Subsystem_1\ADMV1013-044718 RevA\ADMV1013"
    client.Run("@Reset")
    client.Run("@ReadSettings")
    print("Custom logic for ADMV1013 executed.")