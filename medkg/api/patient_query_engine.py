import pandas as pd
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

class PatientQueryEngine:
    def __init__(self, data_path: Union[str, Path] = "data/data_70.xlsx", meta_path: Union[str, Path] = "data/column_meta.json"):
        # Resolve paths relative to project root if they are relative
        # Assuming the code runs from project root or paths are correct. 
        # Making them robust: find project root from this file location
        project_root = Path(__file__).parent.parent.parent
        
        self.data_path = project_root / data_path
        self.meta_path = project_root / meta_path
        
        self.df = None
        self.column_groups = {}
        self.column_definitions = {}
        self.column_map = {}
        self.group_map = {}
        
        self._load_data()
        
    def _load_data(self):
        """Load DataFrame and metadata."""
        try:
            if not self.data_path.exists():
                raise FileNotFoundError(f"Data file not found at {self.data_path}")
            
            # Load Excel file
            self.df = pd.read_excel(self.data_path)
            
            # Load metadata
            if self.meta_path.exists():
                with open(self.meta_path, 'r') as f:
                    meta = json.load(f)
                    self.column_groups = meta.get("column_groups", {})
                    self.column_definitions = meta.get("columns", {})
            else:
                logger.warning(f"Metadata file not found at {self.meta_path}")
                
            # Pre-compute fallback groups if needed (as per requirements)
            # The JSON seems comprehensive, but we can ensure morphology/hemodynamics exist
            if "morphology" not in self.column_groups:
                self.column_groups["morphology"] = [c for c in self.df.columns if "morph" in c.lower() or "size" in c.lower()]
            if "hemodynamics" not in self.column_groups:
                self.column_groups["hemodynamics"] = [c for c in self.df.columns if "wss" in c.lower() or "osi" in c.lower()]
            
            # Pre-convert IDs to string for faster lookup
            if "case_id" in self.df.columns:
                self.df["case_id"] = self.df["case_id"].astype(str)
            if "aneurysm_id" in self.df.columns:
                self.df["aneurysm_id"] = self.df["aneurysm_id"].astype(str)
            
            # Case-insensitive maps
            self.column_map = {c.lower(): c for c in self.df.columns}
            self.group_map = {g.lower(): g for g in self.column_groups.keys()}
            
        except Exception as e:
            logger.error(f"Error loading patient data: {e}")
            # Initialize empty DF to prevent crashes, but log error
            self.df = pd.DataFrame()
            raise e

    def _cast_value(self, value: Any, value_type: str) -> Any:
        """Cast value based on value_type."""
        if value_type == "numeric":
            try:
                if isinstance(value, list):
                    return [float(v) for v in value]
                return float(value)
            except (ValueError, TypeError):
                return value
        elif value_type == "boolean":
            if isinstance(value, str):
                # Robust boolean parsing
                if value.lower() in ("false", "no", "0", "n", "f"):
                    return False
                return True
            return bool(value)
        elif value_type == "range":
            # ranges are usually lists of [min, max]
            return value
        return value
    
    def _resolve_column(self, col_name: str) -> Optional[str]:
        """Resolve column name case-insensitively."""
        if not col_name:
            return None
        return self.column_map.get(col_name.lower())
    
    def _resolve_group(self, group_name: str) -> Optional[str]:
        """Resolve group name case-insensitively."""
        if not group_name:
            return None
        return self.group_map.get(group_name.lower())

    def query_patient_data(
        self,
        select: Dict[str, List[str]],
        entity: Optional[Dict[str, Any]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Query patient data with structured filters and column selection.
        """
        if self.df is None or self.df.empty:
             return {"count": 0, "data": [], "error": "Data not loaded"}

        # Start with full dataframe
        result_df = self.df.copy()

        try:
            # 1. Apply Entity Filter
            if entity:
                entity_type = entity.get("type")
                entity_id = entity.get("id")
                
                # Only apply entity filter if both type and id are provided and non-empty
                if entity_type and entity_id:
                    if entity_type == "case":
                        if "case_id" in result_df.columns:
                            # IDs are already converted to string in _load_data
                            result_df = result_df[result_df["case_id"] == str(entity_id)]
                    elif entity_type == "aneurysm":
                        if "aneurysm_id" in result_df.columns:
                            result_df = result_df[result_df["aneurysm_id"] == str(entity_id)]

            # 2. Apply General Filters
            if filters:
                for f in filters:
                    col_raw = f.get("column")
                    op = f.get("operator")
                    val = f.get("value")
                    val_type = f.get("value_type", "categorical") # default to categorical/string
                    
                    # Resolve column name
                    col = self._resolve_column(col_raw)
                    if not col:
                        continue # Skip invalid columns
                    
                    # Cast value
                    val = self._cast_value(val, val_type)
                    
                    # Apply operator
                    if op == "==":
                        result_df = result_df[result_df[col] == val]
                    elif op == "!=":
                        result_df = result_df[result_df[col] != val]
                    elif op == "<":
                        result_df = result_df[result_df[col] < val]
                    elif op == ">":
                        result_df = result_df[result_df[col] > val]
                    elif op == "<=":
                        result_df = result_df[result_df[col] <= val]
                    elif op == ">=":
                        result_df = result_df[result_df[col] >= val]
                    elif op == "in":
                        if isinstance(val, list):
                            result_df = result_df[result_df[col].isin(val)]
                    elif op == "contains":
                        # Ensure column is string for contains
                        result_df = result_df[result_df[col].astype(str).str.contains(str(val), na=False)]
                    elif op == "between":
                        if isinstance(val, list) and len(val) >= 2:
                            result_df = result_df[result_df[col].between(val[0], val[1])]

            # 3. Select Columns
            selected_columns = set()
            
            # Add requested columns
            if "columns" in select and select["columns"]:
                for col_raw in select["columns"]:
                    col = self._resolve_column(col_raw)
                    if col:
                        selected_columns.add(col)
            
            # Add requested groups
            if "groups" in select and select["groups"]:
                for group_raw in select["groups"]:
                    group = self._resolve_group(group_raw)
                    if group and group in self.column_groups:
                        for col in self.column_groups[group]:
                            if col in self.df.columns:
                                selected_columns.add(col)
            
            # Ensure we have something selected, otherwise return all or default set?
            # Requirement says "Select: Columns to return."
            if not selected_columns:
                # If nothing valid selected, maybe return case_id as minimum?
                if "case_id" in self.df.columns:
                    selected_columns.add("case_id")
            
            final_df = result_df[list(selected_columns)]
            
            # Apply limit
            final_df = final_df.head(limit)
            
            # Convert to dict
            # orient='records' gives list of dicts
            data = final_df.to_dict(orient='records')
            
            return {
                "count": len(data),
                "data": data
            }

        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return {"count": 0, "data": [], "error": str(e)}
