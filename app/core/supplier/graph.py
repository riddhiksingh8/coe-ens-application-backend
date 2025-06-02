from neo4j import AsyncGraphDatabase, exceptions as neo4j_exceptions
import pycountry
from app.core.utils.db_utils import *
from collections import defaultdict
from app.core.config import get_settings

URI = get_settings().graphdb.uri
USER = get_settings().graphdb.user
PASSWORD = get_settings().graphdb.password

def get_country_name(code: str) -> str:
    country = pycountry.countries.get(alpha_2=code.upper())
    return country.name if country else code

# Async Neo4j function
async def get_distinct_supplier_countries(client_id: str):

    fallback_client_id = "5b638302-73cb-4a69-b76d-1efa5c00797a"
    if client_id is None:
        print(f"No Client ID passed, using fallback {fallback_client_id}")
        client_id = fallback_client_id

    if client_id == "string":
        print(f"No Client ID passed, using fallback {fallback_client_id}")
        client_id = fallback_client_id
    driver = None
    try:
        query = """
        MATCH (s:Supplier)-[:SUPPLIER_OF]->(c:Company {id: $client_id})
        WHERE s.country IS NOT NULL
        RETURN DISTINCT s.country AS countryCode
        """
        driver = AsyncGraphDatabase.driver(URI, auth=(USER, PASSWORD))
        async with driver.session() as session:
            result = await session.run(query, client_id=client_id.strip())
            records = await result.data()

        # Extract and map
        response = [
            {"label": get_country_name(rec["countryCode"]), "value": rec["countryCode"]}
            for rec in records
        ]
        return response

    except neo4j_exceptions.Neo4jError as e:
        logger.error(f"Neo4j query failed: {e}")
        return []

    except Exception as e:
        logger.exception(f"Unexpected error while fetching supplier countries: {e}")
        return []

    finally:
        if driver:
            await driver.close()

async def run_graph_retrieval(filter_request:dict):

    fallback_client_id = "5b638302-73cb-4a69-b76d-1efa5c00797a"
    fallback_client_name = "ARAMCO"

    client = filter_request["client"]
    client_id = filter_request["client_id"]
    filter_request.pop("client", None)
    filter_request.pop("client_id", None)

    if client_id is None:
        print(f"No Client ID passed, using fallback {fallback_client_id}")
        client_id = fallback_client_id

    if client_id == "string":
        print(f"No Client ID passed, using fallback {fallback_client_id}")
        client_id = fallback_client_id

    if client is None:
        print(f"No Client Name passed, using fallback {fallback_client_name}")
        client = fallback_client_name

    if client == "string":
        print(f"No Client Name passed, using fallback {fallback_client_name}")
        client = fallback_client_name

    records = await fetch_direct_suppliers(client_id, filter_request)
    transformed_data = await transform_graph_data(records=records, client_id = client_id)

    return transformed_data

async def fetch_direct_suppliers(client_id: str, filters:dict):
    """
    Fetches all suppliers connected to the given client (company) in Neo4j.
    """

    query, params = await build_dynamic_query_for_direct_suppliers(client_id, filters)
    print("Generated Query:", query)
    print("Parameters:", params)

    async with AsyncGraphDatabase.driver(URI, auth=(USER, PASSWORD)) as driver:
        async with driver.session() as session:
            result = await session.run(query,params)
            records = await result.data()

    return records

async def transform_graph_data(records, client_id):

    nodes = []
    links = []

    if len(records)>1:
        print("THIS IS AN ERROR ------> FOUND TWO CLIENT NODES.")

    if len(records) == 0:
        records = await fetch_client_node(client_id)
        record = records[0]
        client_node = record["client"]
        client_node["node_type"] = "Company"
        client_node["node_category"] = "central"
        client_node = apply_central_company_formatting(client_node)
        client_node["query_message"] = "No Results Found for Requested Filters"
        return {"nodes": [client_node], "edges": []}

    record = records[0]

    client_node = record["client"]
    client_node["type"] = "Company"
    client_node["node_category"] = "central"
    suppliers = [{**d, 'node_category': 'direct'} for d in record["suppliers"]]
    individuals = [{**d, 'node_category': 'indirect'} for d in record["individuals"]]

    companies_corp_group = [{**d, 'node_category': 'indirect'} for d in record["companyCorpGroup"]]
    individuals_corp_group = [{**d, 'node_category': 'indirect'} for d in record["individualsCorpGroup"]]

    print(f"Found {len(suppliers)} suppliers")
    print(f"Found {len(individuals)} individuals")

    print(f"Found {len(companies_corp_group)} CG suppliers")
    print(f"Found {len(individuals_corp_group)} CG individuals")

    seen_ids = set()

    # Initialize final list to collect unique nodes
    nodes = []

    # Function to add unique items to final_nodes
    def add_unique_to_final(list_of_nodes):
        for node in list_of_nodes:
            if node['id'] not in seen_ids:
                seen_ids.add(node['id'])
                nodes.append(node)

    # Add all unique suppliers, individuals, and groups
    add_unique_to_final(suppliers)
    add_unique_to_final(individuals)
    add_unique_to_final(companies_corp_group)
    add_unique_to_final(individuals_corp_group)

    # nodes = suppliers + individuals + companies_corp_group + individuals_corp_group
    nodes.append(client_node)

    supplier_relationships = record["supplierRelationships"]
    management_relationships = record["individualRelationships"]

    individuals_relationships_corp_group = record["individualRelationshipsCorpGroup"]
    supplier_relationships_corp_group = record["companyRelationshipsCorpGroup"]

    relationships = supplier_relationships+management_relationships+individuals_relationships_corp_group+supplier_relationships_corp_group
    # print(relationships)
    for i, (related, relationship_type, target) in enumerate(relationships):
        if related["id"] == target['id']:
            continue
        link = {"source": related["id"], "target":target["id"],"relationship_type": relationship_type.replace("_OF","").replace("_"," ")}
        links.append(link)

    links = simple_dedup(links, "source", "target")


    # NODE FORMATTING -> MOVE TO ORCHESTRATION
    nodes = list(nodes)
    final_nodes = []
    for node in nodes:
        # print(node)
        node["node_type"] = node.pop("type")  # rename type to node_type

        if node["node_category"] == "direct":
            if node["node_type"].lower() == "organization":
                modified_node = apply_direct_supplier_formatting(node)
        elif node["node_category"] == "indirect":
            if node["node_type"].lower() == "individual":
                modified_node = apply_person_formatting(node)
                final_nodes.append(modified_node)
            elif node["node_type"].lower() == "organization":
                modified_node = apply_indirect_supplier_formatting(node)
                final_nodes.append(modified_node)
        elif node["node_category"] == "central":
            modified_node = apply_central_company_formatting(node)
            final_nodes.append(modified_node)
    
    return {"nodes": list(nodes), "edges": links}

async def build_dynamic_query_for_direct_suppliers(client_id, filters):
    print("filters", filters)
    # pull out indicators from filters
    view_individuals_with_risk_only = filters.get("individuals_with_risk_only",False)
    filters.pop("view_individuals_with_risk_only", None)
    view_corp_group_with_risk_only = filters.get("corpgroup_with_risk_only",False)
    filters.pop("view_corp_group_with_risk_only", None)

    view_multiple_connections = filters.get("multiple_connections",False)
    filters.pop("multiple_connections", None)

    # first level query aka make sure it is supplier of being pulled out.
    query = """
    MATCH (c:Company {id: $client_id})<-[r:SUPPLIER_OF]-(s:Supplier)
    """

    filter_conditions = []

    # default for our case needs client name at least.
    params = {'client_id': client_id}

    # apply filters on supplier nodes
    for filter_field, filter_value in filters.items():

        if filter_value is None or filter_value == "" or filter_value == "string" or filter_value == ["string"]:
            continue

        filter_condition = None

        if filter_field == "submodal_id":
            filter_field = "id"

        if isinstance(filter_value, list):
            if filter_value == [""]:
                continue
            if len(filter_value) < 1:
                continue
            filter_condition = f"s.{filter_field} IN ${filter_field}"
        elif isinstance(filter_value, str):
            filter_condition = f"s.{filter_field} = ${filter_field}"

        if filter_condition is not None:
            params[filter_field] = filter_value
            filter_conditions.append(filter_condition)

    # --- Type A/B Filtering logic ---
    connection_filters = []
    if filters.get("filter_multiple_connections_direct",False):
        connection_filters.append("""
        EXISTS {
            MATCH (s)-[]-(other:Supplier)-[:SUPPLIER_OF]->(c)
            WHERE s <> other
        }
        """)
    if filters.get("filter_multiple_connections_indirect",False):
        connection_filters.append("""
        EXISTS {
            MATCH (s)-[]-(x)-[]-(other:Supplier)-[:SUPPLIER_OF]->(c)
            WHERE s <> other AND NOT x:Company
        }
        """)

    if connection_filters:
        filter_conditions.append(f"({' OR '.join(connection_filters)})")

    # Final WHERE clause
    if filter_conditions:
        query += " WHERE " + " AND ".join(filter_conditions)

    # Add on individuals nodes matching to this supplier:
    if view_individuals_with_risk_only:
        query += "\nOPTIONAL MATCH (i:Individual)-[r1:MANAGEMENT_OF]->(s)"  # TODO ADD WHERE HERE
    else:
        query += "\nOPTIONAL MATCH (i:Individual)-[r1:MANAGEMENT_OF]->(s)"

    # Add on associated corporate group by using relationship
    if view_corp_group_with_risk_only:
        query += "\nOPTIONAL MATCH (ic:Individual)-[r2:MANAGEMENT_OF|SUBSIDIARY_OF|SHAREHOLDER_OF]->(s)"  # TODO ADD WHERE HERE
        query += "\nOPTIONAL MATCH (cc:Supplier)-[r3:SUBSIDIARY_OF|SHAREHOLDER_OF]->(s)"  # TODO ADD WHERE HERE
    else:
        query += "\nOPTIONAL MATCH (ic:Individual)-[r2:SHAREHOLDER_OF|BENEFICIAL_OWNER_OF|ULTIMATELY_OWNED_SUBSIDIARY_OF|GLOBAL_ULTIMATE_OWNER_OF|OTHER_ULTIMATE_BENEFICIARY_OF]->(s)"
        query += "\nOPTIONAL MATCH (cc:Supplier)-[r3:SHAREHOLDER_OF|BENEFICIAL_OWNER_OF|ULTIMATELY_OWNED_SUBSIDIARY_OF|GLOBAL_ULTIMATE_OWNER_OF|OTHER_ULTIMATE_BENEFICIARY_OF]->(s)"

        # """
        # OPTIONAL MATCH (ss:Supplier)-[:SHAREHOLDER_OF]->(s)
        # OPTIONAL MATCH (si:Individual)-[:SHAREHOLDER_OF]->(s)
        # OPTIONAL MATCH (bi:Individual)-[:BENEFICIAL_OWNER_OF]->(s)
        # OPTIONAL MATCH (bo:Supplier)-[:BENEFICIAL_OWNER_OF]->(s)
        # OPTIONAL MATCH (i:Individual)-[:ULTIMATELY_OWNED_SUBSIDIARY_OF]->(s)
        # OPTIONAL MATCH (so:Supplier)-[:ULTIMATELY_OWNED_SUBSIDIARY_OF]->(s)
        # OPTIONAL MATCH (ii:Individual)-[:GLOBAL_ULTIMATE_OWNER_OF]->(s)
        # OPTIONAL MATCH (soo:Supplier)-[:GLOBAL_ULTIMATE_OWNER_OF]->(s)
        # OPTIONAL MATCH (oui:Individual)-[:OTHER_ULTIMATE_BENEFICIARY_OF]->(s)
        # OPTIONAL MATCH (ou:Supplier)-[:OTHER_ULTIMATE_BENEFICIARY_OF]->(s)
        # """

    query += """
    RETURN c AS client, collect(DISTINCT r) AS supplierRelationships, collect(DISTINCT s) AS suppliers, collect(DISTINCT r1) AS individualRelationships, collect(DISTINCT i) AS individuals
    """

    query += """
    , collect(DISTINCT r2) AS individualRelationshipsCorpGroup, collect(DISTINCT ic) AS individualsCorpGroup, collect(DISTINCT r3) AS companyRelationshipsCorpGroup, collect(DISTINCT cc) AS companyCorpGroup
    """

    print(query, "\n" ,params)

    return query, params


async def fetch_client_node(client_id):

    query = """
    MATCH (c:Company {id: $client_id})
    RETURN c AS client
    """

    params = {'client_id': client_id}

    async with AsyncGraphDatabase.driver(URI, auth=(USER, PASSWORD)) as driver:
        async with driver.session() as session:
            result = await session.run(query,params)
            records = await result.data()

    return records

def apply_person_formatting(node: dict):

    # Risk Indicator for Person
    node["risk_indicator"] = "false"
    node["node_colour"] = "#dadde0"# "#BCCCDC"

    node["node_size"] = 2
    if (node.get("sanctions_indicator") == "true") or (node.get("pep_indicator") == "true") or (node.get("media_indicator") == "true"):
        node["risk_indicator"] = "true"
        node["node_colour"] = _convert_score_to_hex_gradient(score=0.01, rating="High")
        node["node_size"] = 10
        risks = []
        if node.get("sanctions_indicator") == "true":
            risks.append("Sanctions/Watchlist Exposure")
        if node.get("pep_indicator") == "true":
            risks.append("PeP")
        if node.get("media_indicator") == "true":
            risks.append("Adverse Media")
        desc = "Risks: " + ", ".join(risks)
        node["node_risk_description"] = desc


    return node

def apply_indirect_supplier_formatting(node: dict):

    # Risk Indicator for Person 
    node["risk_indicator"] = "false"
    node["node_colour"] = "#C3D6E4"

    node["node_size"] = 5
    if (node.get("sanctions_indicator") == "true") or (node.get("pep_indicator") == "true") or (node.get("media_indicator") == "true"):
        node["risk_indicator"] = "true"
        node["node_colour"] = _convert_score_to_hex_gradient(score=0.01, rating="High")
        node["node_size"] = 10
        risks = []
        if node.get("sanctions_indicator") == "true":
            risks.append("Sanctions/Watchlist Exposure")
        if node.get("pep_indicator") == "true":
            risks.append("PeP")
        if node.get("media_indicator") == "true":
            risks.append("Adverse Media")
        desc = "Risks: " + ", ".join(risks)
        node["node_risk_description"] = desc

    return node

def apply_direct_supplier_formatting(node: dict):

    rating_theme_weightage = {
        "sanctions_rating":3,
        "government_political_rating":3,
        "bribery_corruption_overall_rating":2,
        "other_adverse_media_rating":2,
        "financials_rating": 2,
        "additional_indicator_rating":1,
    }

    rating_weightage = {
        "High":10,
        "Medium":5,
        "Low":1,
        "No Alerts":0
    }

    maximum_range = 0
    minimum_range = 0
    for rating_type, rating_weight in rating_theme_weightage.items():
        maximum_range += rating_weightage["High"]*rating_weight

    weighted_rating_score = 0
    for rating_type, rating_value in node.items():
        if rating_type in rating_theme_weightage.keys():
            weighted_rating_score += rating_theme_weightage[rating_type]*rating_weightage[rating_value]

    # print(weighted_rating_score)

    overall_rating = node.get("overall_rating")
    if overall_rating == "High":
        scale_max = 100
        scale_min = 50
    elif overall_rating == "Medium":
        scale_max = 50
        scale_min = 10
    elif overall_rating == "Low":
        scale_max = 10
        scale_min = 0
    else:
        scale_max = 10
        scale_min = 0

    # print(overall_rating, scale_min, scale_max)

    scaled_score = (weighted_rating_score-minimum_range)/(maximum_range-minimum_range)

    scaled_weighted_rating_score = (((weighted_rating_score-minimum_range) * (scale_max-scale_min))/(maximum_range-minimum_range))+scale_min
    scaled_weighted_rating_score = round(scaled_weighted_rating_score)

    # print(scaled_weighted_rating_score, scaled_score)

    node["risk_intensity_score"] = scaled_weighted_rating_score
    node["node_colour"] = _convert_score_to_hex_gradient(scaled_score, overall_rating)
    node["node_size"] = 200

    return node

def apply_central_company_formatting(node:dict):

    node["node_colour"] = "#0da8ea"
    node["node_size"] = 450

    return node

def _convert_score_to_hex_gradient(score, rating):

    if rating == "Low":
        start_rgb = (90, 129, 20)
        end_rgb = (185, 219, 101)
        hex_colour = _interpolate_rgb(start_rgb, end_rgb, score)
    elif rating == "Medium": # Yellow
        start_rgb = (255, 214, 58)
        end_rgb = (247, 152, 33)
        hex_colour = _interpolate_rgb(start_rgb, end_rgb, score)
    elif rating == "High":
        start_rgb = (236, 108, 89)
        end_rgb = (197, 37, 37)
        hex_colour = _interpolate_rgb(start_rgb, end_rgb, score)
    else:
        hex_colour = "#BCCCDC"


    return hex_colour

def _interpolate_rgb(start_rgb, end_rgb, t):
    r1, g1, b1 = start_rgb
    r2, g2, b2 = end_rgb

    r = int(r1 + t * (r2 - r1))
    g = int(g1 + t * (g2 - g1))
    b = int(b1 + t * (b2 - b1))

    hex_colour = f"#{r:02x}{g:02x}{b:02x}"

    return hex_colour


async def compile_company_profile(ens_id:str, session):

    latest_session_id, update_time = await pull_latest_session_id(ens_id, session)

    profile = await pull_profile(ens_id,  latest_session_id, session)
    ratings = await pull_ratings(ens_id,  latest_session_id, session)

    compiled_findings = {
        "profile": profile,
        "ratings": ratings,
        "metadata": {
            "ens_id": ens_id,
            "latest_session_id": latest_session_id,
            "latest_screening_time": update_time
        }
    }

    return compiled_findings


async def compile_company_findings(ens_id: str, session):

    latest_session_id, update_time = await pull_latest_session_id(ens_id, session)

    profile = await pull_profile(ens_id,  latest_session_id, session)
    ratings = await pull_ratings(ens_id,  latest_session_id, session)
    findings = await pull_kpis(ens_id,  latest_session_id, session)

    compiled_findings = {
        "profile": profile,
        "ratings": ratings,
        "findings": findings,
        "metadata": {
            "ens_id": ens_id,
            "latest_session_id": latest_session_id,
            "latest_screening_time": update_time
        }
    }

    return compiled_findings


async def compile_company_financials(ens_id: str, session):
    latest_session_id, update_time = await pull_latest_session_id(ens_id, session)
    profile = await pull_profile(ens_id, latest_session_id, session)
    ratings = await pull_ratings(ens_id, latest_session_id, session)
    all_financial_data = await pull_financial_metrics(ens_id, latest_session_id, session)

    METRIC_CATEGORIES = {
        "PROFIT & LOSS ACCOUNT": [
            "operating_revenue", "profit_loss_after_tax",
            "ebitda", "cash_flow", "pl_before_tax"
        ],
        "BALANCE SHEET": [
            "shareholders_fund", "total_assets"
        ],
        "STRUCTURE RATIOS": [
            "current_ratio", "solvency_ratio"
        ],
        "PROFITABILITY RATIOS": [
            "roce_before_tax", "roe_before_tax",
            "roe_using_net_income", "profit_margin"
        ]
    }

    def format_value(value, metric_name):
        try:
            if value is None:
                return None


            if any(x in metric_name for x in ['ratio', 'roce', 'roe', 'margin']):
                return f"{float(entry["value"]):.2f}%"

            value_usd = float(value) * 1000
            abs_value = abs(value_usd)
            if abs_value >= 1_000_000_000:
                return f"${value_usd / 1_000_000_000:.2f}B USD"
            elif abs_value >= 1_000_000:
                return f"${value_usd / 1_000_000:.2f}M USD"
            else:
                return f"${value_usd:,.2f} USD"
        except:
            return str(value)

    financials = {}
    for category, metrics in METRIC_CATEGORIES.items():
        for metric in metrics:
            if metric not in all_financial_data:
                continue

            title = metric.replace('_', ' ').title() \
                .replace('Ebitda', 'EBITDA') \
                .replace('Pl ', 'PL ') \
                .replace('Roce', 'ROCE') \
                .replace('Roe', 'ROE')

            formatted_data = []
            for entry in all_financial_data[metric]:
                formatted_data.append({
                    "display_value": format_value(entry["value"], metric),
                    "raw_value": float(entry["value"]) if category in ['STRUCTURE RATIOS','PROFITABILITY RATIOS'] else float(entry["value"])*1000,
                    "closing_date": entry["closing_date"]
                })

            financials[metric] = {
                "title": title,
                "category": category,
                "data": sorted(formatted_data, key=lambda x: x["closing_date"], reverse=True)
            }

    return {
        "profile": profile,
        "ratings": ratings,
        "financials": financials,
        "metadata": {
            "ens_id": ens_id,
            "latest_session_id": latest_session_id,
            "update_time": update_time
        }
    }

async def compile_company_timeline(ens_id: str, session):

    latest_session_id, update_time = await pull_latest_session_id(ens_id, session)

    profile = await pull_profile(ens_id,  latest_session_id, session)
    ratings = await pull_ratings(ens_id,  latest_session_id, session)
    timeline = {}

    compiled_findings = {
        "profile": profile,
        "ratings": ratings,
        "timeline": timeline,
        "metadata": {
            "ens_id": ens_id,
            "latest_session_id": latest_session_id
        }
    }

    return compiled_findings


async def pull_latest_session_id(ens_id: str, session):

    # GET THE LATEST COMPLETED SESSION
    session_id_row = await get_latest_session_for_ens_id("ensid_screening_status", required_columns=["session_id", "overall_status"],ens_id=ens_id, session=session)
    session_id = session_id_row[0].get("session_id")
    update_time = session_id_row[0].get("update_time")

    return session_id, update_time

async def pull_profile(ens_id: str, latest_session_id: str, session):

    copr_required_cols = ["employee", "name", "location", "address", 'website', 'active_status', 'operation_type',
                          'legal_status', 'national_identifier', 'alias', 'incorporation_date', 'revenue',
                          'subsidiaries', 'corporate_group', 'shareholders', 'key_executives']
    copr = await get_dynamic_ens_data_for_session('company_profile', copr_required_cols, ens_id, latest_session_id, session)
    copr = copr[0]

    return copr


async def pull_ratings(ens_id: str, latest_session_id: str, session):

    required_columns = ["kpi_area", "kpi_code", "kpi_definition", "kpi_rating", "update_time"]
    res_ratings = await get_dynamic_ens_data_for_session("ovar", required_columns, ens_id, latest_session_id, session)
    theme_ratings = {}
    for rating_row in res_ratings:
        if rating_row.get("kpi_rating", "").lower() != "deactivated":
            theme_ratings.update({
                rating_row.get("kpi_code", "").replace(" ", "_"): rating_row.get("kpi_rating", "")
            })

    return theme_ratings

async def pull_kpis(ens_id: str, session_id: str, session):

        theme_mappings = {
            "sanctions": ["SAN"],
            "government_political": ["PEP", "SCO"],
            "bribery_corruption_overall": ["BCF"],
            "financials": ["FIN", "BKR"],
            "other_adverse_media": ["NWS", "AMR", "AMO", "ONF"],
            "additional_indicator": ["CYB", "ESG", "WEB"]
        } # change this to from DB

        reverse_area_mapping = {code: theme for theme, codes in theme_mappings.items() for code in codes}

        required_columns = ["kpi_area", "kpi_code", "kpi_definition", "kpi_rating", "kpi_flag", "kpi_details"]
        kpi_table_name = ['cyes', 'fstb', 'lgrk', 'oval', 'rfct', 'sape', 'sown', 'news']

        gather_all_kpis = []
        for table_name in kpi_table_name:
            res_kpis = await get_dynamic_ens_data_for_session(table_name, required_columns, ens_id, session_id, session)
            gather_all_kpis.extend(res_kpis)

        grouped_data = defaultdict(list)
        for theme in theme_mappings:
            grouped_data[theme] = []

        for item in gather_all_kpis:
            if item['kpi_flag']:
                kpi_theme = reverse_area_mapping.get(item['kpi_area'], False)  # get theme if in current mapping
                if kpi_theme:
                    grouped_data[kpi_theme].append(item)

        screening_kpis_dict = dict(grouped_data)

        return screening_kpis_dict


async def pull_financial_metrics(ens_id: str, latest_session_id: str, session):

    financial_metrics = [ "operating_revenue", "profit_loss_after_tax", "ebitda", "cash_flow", "pl_before_tax",
            "roce_before_tax", "roe_before_tax", "roe_using_net_income", "profit_margin",
            "shareholders_fund", "total_assets", "current_ratio", "solvency_ratio"
    ]

    financial_data = await get_dynamic_ens_data_for_session("external_supplier_data", financial_metrics, ens_id, latest_session_id, session )

    result = {}
    for record in financial_data:
        for metric_column in financial_metrics:
            metric_values = record.get(metric_column, [])

            if not isinstance(metric_values, list):
                metric_values = []

            result[metric_column] = metric_values

    return result

def simple_dedup(data, key1, key2):
    seen = set()
    result = []

    for item in data:
        key = (item[key1], item[key2])
        if key not in seen:
            seen.add(key)
            result.append(item)

    return result
