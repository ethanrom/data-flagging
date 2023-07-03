import streamlit as st
import pandas as pd
import base64

def calculate_allocations(shortages_df, excesses_df):
    shortages_df = shortages_df.sort_values(by='Supply new needed', ascending=False)
    excesses_df = excesses_df[excesses_df['Location Type'] == 'MAIN']
    excesses_df['Excess-Usage Index'] = excesses_df.apply(lambda row: row['EXCESS'] * (1/row['Avg Usage + Usage via dependents']) if row['Avg Usage + Usage via dependents'] != 0 else row['EXCESS'], axis=1)
    excesses_df = excesses_df.sort_values(by='Excess-Usage Index', ascending=False)
    allocations = []

    for _, shortage_row in shortages_df.iterrows():
        part_id = shortage_row['Client Warehouse code']
        shortage = shortage_row['Supply new needed']
        transferred_qty = 0

        for _, excess_row in excesses_df.iterrows():
            if transferred_qty >= shortage:
                break
            if excess_row['EXCESS'] > 0:
                transfer_qty = min(shortage - transferred_qty, excess_row['EXCESS'])
                excesses_df.at[excess_row.name, 'EXCESS'] -= transfer_qty
                excesses_df.at[excess_row.name, 'Excess-Usage Index'] = excesses_df.at[excess_row.name, 'EXCESS'] * \
                    (1/excesses_df.at[excess_row.name, 'Avg Usage + Usage via dependents']) if excesses_df.at[excess_row.name, 'Avg Usage + Usage via dependents'] != 0 else \
                    excesses_df.at[excess_row.name, 'EXCESS']
                allocations.append({
                    'From': excess_row['Client Warehouse code'],
                    'To': shortage_row['Client Warehouse code'],
                    'Part ID': part_id,
                    'Quantity': transfer_qty
                })
                transferred_qty += transfer_qty

        if transferred_qty < shortage:
            shortages_df.at[shortage_row.name, 'Supply new needed'] = shortage - transferred_qty

    unfulfilled_shortages = shortages_df[shortages_df['Supply new needed'] > 0]
    excesses_df['Excess-Usage Index'] = excesses_df.apply(lambda row: row['EXCESS'] * (1/row['Avg Usage + Usage via dependents']) if row['Avg Usage + Usage via dependents'] != 0 else row['EXCESS'], axis=1)

    return allocations, unfulfilled_shortages

def main():
    st.title("Allocation App")
    option = st.sidebar.selectbox("Choose an option:", ("Load Example File", "Upload New File"))

    if option == "Load Example File":
        file_path = "sample.xlsx"
    else:
        uploaded_file = st.sidebar.file_uploader("Upload an Excel file", type=["xlsx"])
        if uploaded_file is not None:
            try:
                with st.spinner('Processing the uploaded file...'):
                    with open("temp.xlsx", "wb") as f:
                        f.write(uploaded_file.getvalue())

                    file_path = "temp.xlsx"
            except Exception as e:
                st.error("Error: Unable to process the uploaded file.")
                st.error(str(e))
                return
        else:
            st.info("Please upload an Excel file.")
            return

    try:
        with st.spinner('Loading data...'):
            xl = pd.ExcelFile(file_path)
            shortages_df = xl.parse("Shortages")
            excesses_df = xl.parse("Excesses")
            allocations, unfulfilled_shortages = calculate_allocations(shortages_df, excesses_df)
            final_shortages = shortages_df.copy()
            final_shortages.loc[unfulfilled_shortages.index, 'Status'] = 'Unfulfilled'

        st.subheader("Search")
        search_text = st.text_input("Enter search text", "")

        st.subheader("Allocations")
        allocations_df = pd.DataFrame(allocations)
        if not search_text:
            st.dataframe(allocations_df)
        else:
            filtered_allocations_df = allocations_df[allocations_df.astype(str).apply(lambda x: x.str.contains(search_text, case=False)).any(axis=1)]
            if filtered_allocations_df.empty:
                st.warning("No matching records found.")
            else:
                st.dataframe(filtered_allocations_df)

        st.subheader("Unfulfilled Shortages")
        if not search_text:
            if unfulfilled_shortages.empty:
                st.info("No unfulfilled shortages.")
            else:
                st.dataframe(unfulfilled_shortages)
        else:
            filtered_unfulfilled_shortages = unfulfilled_shortages[unfulfilled_shortages.astype(str).apply(lambda x: x.str.contains(search_text, case=False)).any(axis=1)]
            if filtered_unfulfilled_shortages.empty:
                st.warning("No matching records found.")
            else:
                st.dataframe(filtered_unfulfilled_shortages)

        st.subheader("Transfers Made")
        transfers_df = allocations_df.copy()
        transfers_df['Transfer'] = transfers_df['Part ID'] + ' || ' + transfers_df['From'] + ' --> ' + transfers_df['Part ID'] + ' || ' + transfers_df[
            'To'] + ' x ' + transfers_df['Quantity'].astype(str)
        if not search_text:
            st.dataframe(transfers_df[['Transfer']])
        else:
            filtered_transfers_df = transfers_df[transfers_df.astype(str).apply(lambda x: x.str.contains(search_text, case=False)).any(axis=1)]
            if filtered_transfers_df.empty:
                st.warning("No matching records found.")
            else:
                st.dataframe(filtered_transfers_df[['Transfer']])

        final_shortages.rename(columns={'Client Warehouse code': 'Part ID'}, inplace=True)
        st.subheader("Final Rolling Shortage")
        if not search_text:
            if final_shortages.empty:
                st.info("No final rolling shortage.")
            else:
                st.dataframe(final_shortages)
        else:
            filtered_final_shortages = final_shortages[final_shortages.astype(str).apply(lambda x: x.str.contains(search_text, case=False)).any(axis=1)]
            if filtered_final_shortages.empty:
                st.warning("No matching records found.")
            else:
                st.dataframe(filtered_final_shortages)

        # Download options
        download_options(allocations_df, "Allocations")
        download_options(unfulfilled_shortages, "Unfulfilled Shortages")
        download_options(transfers_df[['Transfer']], "Transfers Made")
        download_options(final_shortages, "Final Rolling Shortage")

    except Exception as e:
        st.error("Error: Unable to process the file.")
        st.error(str(e))

def download_options(data, name):
    csv = data.to_csv(index=False).encode()
    b64 = base64.b64encode(csv).decode()

    st.markdown(f'<a href="data:file/csv;base64,{b64}" download="{name}.csv">Download {name} as CSV</a>', unsafe_allow_html=True)

if __name__ == '__main__':
    main()
