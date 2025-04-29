def logic(client):
    """Custom logic for ADMV1013."""
    client.ContextPath = "\System\Subsystem_1\ADMV1013-044718 RevA\ADMV1013"
    #client.SetIntParameter("QUAD_SE_MODE", "6", "-1")
    #client.SetDecimalParameter("virtual-parameter-quadfilter", "5", "-1")
    #client.Run("@ApplySettings")
    client.Run("@ReadSettings")
    print("Custom logic for ADMV1013 executed.")