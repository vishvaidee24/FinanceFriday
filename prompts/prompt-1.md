End Goal: Multiple data sources all ingested into the database. With daily spot checks with n = 32 across the various tables. Create a metabase dashboard to view this information.

Step 3: Ingest SPY/QQQ only stock data from the last 3 years in a similar fashion to INTC/SOFI. Automate the ingestion from Alpaca.

Step 4: Ingest WMT/DIS stock data, news stories, insider transactions, bonds, analyst rating from the last 3 years in a similar fashion to INTC/SOFI. Automate the ingestion from Alpaca.


Step 7: I need a data dump of the tables under the market schema that is stored in google drive. the csv file should be dumped per table one time to the drive folder. after that the csv should be updated to only append daily data without changing other data. prompt me for access to the drive account where i want the csv to be stored. this should be automated and will serve as a backup.


Step 8: Terraform deploy a new ec2 instance. deploy a Metabase docker container to the instance. Give Metabase a read-only finance-data account. Grant it access to the RDS tables but not permission to modify ingested data. Limit the network access. Set the RDS security group to allow PostgreSQL connections only from the Metabase EC2 security group. For now lets keep metabase dashboard only accessible from SSM portforwarding session. later we will migrate it to be available to open internet. when migrating to open internet i will need to setup login information for a few users.
