from app.providers.sec import SecProvider


def test_parses_form4_and_keeps_sale_signal_unclear() -> None:
    xml = b"""<ownershipDocument><reportingOwner><reportingOwnerId><rptOwnerCik>123</rptOwnerCik><rptOwnerName>DOE JANE</rptOwnerName></reportingOwnerId><reportingOwnerRelationship><isDirector>1</isDirector></reportingOwnerRelationship></reportingOwner><nonDerivativeTable><nonDerivativeTransaction><securityTitle><value>Common Stock</value></securityTitle><transactionDate><value>2026-09-20</value></transactionDate><transactionCoding><transactionCode>S</transactionCode></transactionCoding><transactionAmounts><transactionShares><value>100</value></transactionShares><transactionPricePerShare><value>25.50</value></transactionPricePerShare><transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode></transactionAmounts><postTransactionAmounts><sharesOwnedFollowingTransaction><value>900</value></sharesOwnedFollowingTransaction></postTransactionAmounts><ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature></nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>"""
    rows = SecProvider.parse_ownership_document(
        xml,
        accession_number="0001-26-000001",
        filing_date="2026-09-21",
        source_url="https://www.sec.gov/example.xml",
    )
    assert len(rows) == 1
    assert rows[0].person_name == "DOE JANE"
    assert rows[0].transaction_value == 2550
    assert rows[0].signal == "unclear"
