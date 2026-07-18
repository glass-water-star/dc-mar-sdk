def test_sdk_namespace_exports_client():
    import dc_mar_sdk
    from dc_mar_sdk import DCMarClient
    from dc_mar_sdk.client import DCMarClient as ClientFromSubmodule

    assert dc_mar_sdk.DCMarClient is DCMarClient
    assert ClientFromSubmodule is DCMarClient
    assert dc_mar_sdk.MARClient is DCMarClient
